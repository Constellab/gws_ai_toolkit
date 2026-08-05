"""The knowledge-base chat loop, driven end to end without an API call or a database write.

The model is a ``FunctionModel`` scripted to call ``search_knowledge`` and then answer, and the
retriever is a stub. Between them they cover what the loop actually owns: the yielded message
sequence, the scoping of a retrieval, the sources attached to the answer, the tool turns a restore
replays, and the error path.
"""

from dataclasses import dataclass, field

from gws_ai_toolkit.models.chat.conversation.base_chat_conversation import (
    BaseChatConversationConfig,
    ChatConversationMode,
)
from gws_ai_toolkit.models.chat.conversation.knowledge_base_chat_conversation import (
    KnowledgeBaseChatConversation,
)
from gws_ai_toolkit.models.chat.message.chat_message_error import ChatMessageError
from gws_ai_toolkit.models.chat.message.chat_message_source import ChatMessageSource
from gws_ai_toolkit.models.chat.message.chat_message_streaming import ChatMessageStreaming
from gws_ai_toolkit.models.chat.message.chat_message_text import ChatMessageText
from gws_ai_toolkit.models.chat.message.chat_message_tool_call import ChatMessageToolCall
from gws_ai_toolkit.models.chat.message.chat_message_tool_result import ChatMessageToolResult
from gws_ai_toolkit.models.chat.message.chat_user_message import ChatUserMessageText
from gws_ai_toolkit.models.knowledge_base.knowledge_base_agent_ai import (
    SEARCH_KNOWLEDGE_TOOL_NAME,
    KnowledgeBaseAgentAi,
)
from gws_ai_toolkit.models.knowledge_base.knowledge_base_chat_config import KnowledgeBaseChatConfig
from gws_ai_toolkit.models.knowledge_base.knowledge_base_retriever import KnowledgeBaseRetriever
from gws_ai_toolkit.rag.knowledge_base.knowledge_base_models import RetrievedChunk
from gws_core import BaseTestCase
from pydantic_ai.messages import TextPart, ToolCallPart, ToolReturnPart, UserPromptPart

from .agent_test_helper import ScriptedAnswer, ScriptedTurn, SingleAgentScriptedModel, ToolCall

CHAT_APP_NAME = "test_knowledge_base_chat"
KNOWLEDGE_BASE_ID = "kb-1"


def build_chunk(chunk_id: str, content: str, score: float = 0.03) -> RetrievedChunk:
    """A retrieved chunk, with the fields the source pill and the chunk dialog read."""
    return RetrievedChunk(
        chunk_id=chunk_id,
        content=content,
        score=score,
        knowledge_base_id=KNOWLEDGE_BASE_ID,
        document_id=f"doc-{chunk_id}",
        filename=f"{chunk_id}.md",
    )


def search(query: str) -> ToolCall:
    """A scripted ``search_knowledge`` call."""
    return ToolCall(SEARCH_KNOWLEDGE_TOOL_NAME, {"query": query})


@dataclass
class StubRetriever(KnowledgeBaseRetriever):
    """A retriever answering from a script, recording how it was called.

    Attributes:
        results: Chunks to return, one entry per search. The last entry answers any further search.
        error: Raised instead of returning, to exercise the error path.
        calls: The arguments of every search, so a test can assert the scoping.
    """

    results: list[list[RetrievedChunk]] = field(default_factory=list)
    error: Exception | None = None
    calls: list[dict] = field(default_factory=list)

    def retrieve(
        self,
        query: str,
        knowledge_base_ids: list[str],
        top_k: int = 5,
        score_threshold: float | None = None,
        document_ids: list[str] | None = None,
    ) -> list[RetrievedChunk]:
        self.calls.append(
            {
                "query": query,
                "knowledge_base_ids": knowledge_base_ids,
                "top_k": top_k,
                "score_threshold": score_threshold,
                "document_ids": document_ids,
            }
        )
        if self.error:
            raise self.error
        if not self.results:
            return []
        index = min(len(self.calls) - 1, len(self.results) - 1)
        return self.results[index]


# test_knowledge_base_chat_conversation
class TestKnowledgeBaseChatConversation(BaseTestCase):
    """The chat loop, with no API call and no database write."""

    def _build_conversation(
        self,
        retriever: StubRetriever,
        turns: list[ScriptedAnswer],
        top_k: int = 5,
        score_threshold: float | None = None,
        knowledge_base_ids: list[str] | None = None,
    ) -> tuple[KnowledgeBaseChatConversation, KnowledgeBaseAgentAi, SingleAgentScriptedModel]:
        """A conversation driven by a scripted model, persisting nothing."""
        scripted_model = SingleAgentScriptedModel(turns=turns)
        agent = KnowledgeBaseAgentAi(
            chat_config=KnowledgeBaseChatConfig(
                chat_profile_id="profile-1",
                model="openai:gpt-4.1-mini",
                system_prompt="Search before answering.",
                top_k=top_k,
                score_threshold=score_threshold,
                knowledge_base_ids=(
                    [KNOWLEDGE_BASE_ID] if knowledge_base_ids is None else knowledge_base_ids
                ),
            ),
            retriever=retriever,
            model=scripted_model.build(),
        )
        conversation = KnowledgeBaseChatConversation(
            config=BaseChatConversationConfig(CHAT_APP_NAME, store_conversation_in_db=False),
            knowledge_agent=agent,
        )
        conversation.create_conversation("A question")
        return conversation, agent, scripted_model

    def test_a_question_streams_an_answer_and_closes_it_with_its_sources(self):
        """user → streaming* → a source message carrying what was retrieved."""
        retriever = StubRetriever(
            results=[[build_chunk("chunk-1", "The report says X."), build_chunk("chunk-2", "And Y.")]]
        )
        conversation, _, scripted_model = self._build_conversation(
            retriever, turns=[search("report"), "The report says X and Y."]
        )

        messages = list(
            conversation.call_conversation(ChatUserMessageText(content="What does the report say?"))
        )

        # The model was offered the retrieval tool...
        self.assertEqual(scripted_model.tool_names_seen[0], [SEARCH_KNOWLEDGE_TOOL_NAME])
        # ...and it searched with what it was told to search for.
        self.assertEqual(len(retriever.calls), 1)
        self.assertEqual(retriever.calls[0]["query"], "report")

        self.assertIsInstance(messages[0], ChatUserMessageText)

        streamed = [message for message in messages if isinstance(message, ChatMessageStreaming)]
        self.assertTrue(streamed, "the answer must reach the UI as it is produced")
        self.assertEqual(streamed[-1].content, "The report says X and Y.")

        final_message = messages[-1]
        self.assertIsInstance(final_message, ChatMessageSource)
        self.assertEqual(final_message.content, "The report says X and Y.")
        self.assertEqual(
            [source.document_name for source in final_message.sources],
            ["chunk-1.md", "chunk-2.md"],
        )
        self.assertEqual(
            [source.chunk.chunk_id for source in final_message.sources], ["chunk-1", "chunk-2"]
        )
        self.assertEqual(final_message.sources[0].chunk.content, "The report says X.")

        # The mode is what a restore dispatches on, and the profile is what it restores from.
        self.assertEqual(conversation.mode, ChatConversationMode.KNOWLEDGE_BASE.value)
        self.assertEqual(
            conversation.chat_configuration[
                KnowledgeBaseChatConversation.CHAT_PROFILE_ID_CONFIG_KEY
            ],
            "profile-1",
        )

    def test_a_focused_message_scopes_retrieval_to_its_documents(self):
        """Document Focus (issue #29): a message carrying focus narrows every search of its turn."""
        retriever = StubRetriever(results=[[build_chunk("chunk-1", "About the budget.")]])
        conversation, _, _ = self._build_conversation(
            retriever, turns=[search("budget"), "Here it is."]
        )

        list(
            conversation.call_conversation(
                ChatUserMessageText(
                    content="What is the budget?", focused_document_ids=["doc-1", "doc-2"]
                )
            )
        )

        self.assertEqual(retriever.calls[0]["document_ids"], ["doc-1", "doc-2"])

    def test_an_unfocused_message_searches_without_a_document_filter(self):
        """No focus set on the message means no ``document_ids`` filter reaches the retriever."""
        retriever = StubRetriever(results=[[build_chunk("chunk-1", "About the budget.")]])
        conversation, _, _ = self._build_conversation(
            retriever, turns=[search("budget"), "Here it is."]
        )

        list(conversation.call_conversation(ChatUserMessageText(content="What is the budget?")))

        self.assertIsNone(retriever.calls[0]["document_ids"])

    def test_retrieval_is_scoped_to_the_profile_and_honours_its_limits(self):
        """The bound knowledge bases, top_k and the threshold all reach the retrieval."""
        retriever = StubRetriever(results=[[build_chunk("chunk-1", "A passage.")]])
        conversation, _, _ = self._build_conversation(
            retriever,
            turns=[search("budget"), "Here it is."],
            top_k=3,
            score_threshold=0.02,
            knowledge_base_ids=["kb-a", "kb-b"],
        )

        list(conversation.call_conversation(ChatUserMessageText(content="What is the budget?")))

        self.assertEqual(retriever.calls[0]["knowledge_base_ids"], ["kb-a", "kb-b"])
        self.assertEqual(retriever.calls[0]["top_k"], 3)
        self.assertEqual(retriever.calls[0]["score_threshold"], 0.02)

    def test_a_passage_retrieved_twice_becomes_one_source(self):
        """Two searches returning the same chunk must not show the reader two pills."""
        shared_chunk = build_chunk("chunk-1", "The same passage.")
        retriever = StubRetriever(
            results=[[shared_chunk], [shared_chunk, build_chunk("chunk-2", "Another one.")]]
        )
        conversation, _, _ = self._build_conversation(
            retriever,
            turns=[search("first wording"), search("second wording"), "Both agree."],
        )

        messages = list(
            conversation.call_conversation(ChatUserMessageText(content="Compare both wordings"))
        )

        self.assertEqual(len(retriever.calls), 2)

        final_message = messages[-1]
        self.assertIsInstance(final_message, ChatMessageSource)
        self.assertEqual(
            [source.chunk.chunk_id for source in final_message.sources], ["chunk-1", "chunk-2"]
        )

    def test_only_the_answer_carries_the_sources(self):
        """A model that speaks before searching must not have its preamble sourced too."""
        retriever = StubRetriever(results=[[build_chunk("chunk-1", "The report says X.")]])
        conversation, _, _ = self._build_conversation(
            retriever,
            turns=[
                ScriptedTurn(text="Let me look that up. ", tool_call=search("report")),
                "The report says X.",
            ],
        )

        messages = list(
            conversation.call_conversation(ChatUserMessageText(content="What does the report say?"))
        )

        # The preamble is its own message, and the sources belong to the answer alone.
        sourced = [message for message in messages if isinstance(message, ChatMessageSource)]
        self.assertEqual(len(sourced), 1)
        self.assertEqual(sourced[0].content, "The report says X.")
        self.assertEqual([source.chunk.chunk_id for source in sourced[0].sources], ["chunk-1"])

        recorded = [message.message_type for message in conversation.chat_messages]
        self.assertEqual(recorded, ["user-text", "text", "tool_call", "tool_result", "source"])
        self.assertEqual(recorded.count("source"), 1)

    def test_the_tool_turns_are_recorded_before_the_answer_they_led_to(self):
        """A search is persisted as a call/result pair, in the order a restore replays."""
        retriever = StubRetriever(results=[[build_chunk("chunk-1", "The answer is X.")]])
        conversation, _, _ = self._build_conversation(
            retriever, turns=[search("answer"), "It is X."]
        )

        list(conversation.call_conversation(ChatUserMessageText(content="What is the answer?")))

        recorded = [message.message_type for message in conversation.chat_messages]
        self.assertEqual(recorded, ["user-text", "tool_call", "tool_result", "source"])

        tool_call = conversation.chat_messages[1]
        tool_result = conversation.chat_messages[2]
        self.assertIsInstance(tool_call, ChatMessageToolCall)
        self.assertIsInstance(tool_result, ChatMessageToolResult)
        self.assertEqual(tool_call.tool_name, SEARCH_KNOWLEDGE_TOOL_NAME)
        self.assertEqual(tool_call.args, {"query": "answer"})
        self.assertEqual(tool_call.tool_call_id, tool_result.tool_call_id)
        self.assertIn("The answer is X.", tool_result.content)

        # None of it is shown to the user.
        visible = [message.message_type for message in conversation.get_visible_messages()]
        self.assertEqual(visible, ["user-text", "source"])

    def test_a_search_the_model_had_to_correct_stays_paired(self):
        """A tool error is the result of that call, so the retry that followed restores cleanly."""
        retriever = StubRetriever(results=[[build_chunk("chunk-1", "The answer is X.")]])
        conversation, _, _ = self._build_conversation(
            retriever, turns=[search("   "), search("answer"), "It is X."]
        )

        list(conversation.call_conversation(ChatUserMessageText(content="What is the answer?")))

        # The empty query never reached the retriever, but it was still recorded and answered.
        self.assertEqual([call["query"] for call in retriever.calls], ["answer"])

        tool_calls = [
            message
            for message in conversation.chat_messages
            if isinstance(message, ChatMessageToolCall)
        ]
        tool_results = [
            message
            for message in conversation.chat_messages
            if isinstance(message, ChatMessageToolResult)
        ]
        self.assertEqual(len(tool_calls), 2)
        self.assertEqual(len(tool_results), 2)
        self.assertIn("No query provided", tool_results[0].content)
        self.assertEqual(
            [call.tool_call_id for call in tool_calls],
            [result.tool_call_id for result in tool_results],
        )

    def test_restoring_a_conversation_replays_its_tool_turns(self):
        """A restored conversation hands the model back what it already retrieved."""
        conversation, agent, _ = self._build_conversation(
            StubRetriever(), turns=["Nothing to do."]
        )

        conversation.restore_messages(
            [
                ChatUserMessageText(content="What does the report say?"),
                ChatMessageToolCall(
                    tool_name=SEARCH_KNOWLEDGE_TOOL_NAME,
                    args={"query": "report"},
                    tool_call_id="call_1",
                ),
                ChatMessageToolResult(
                    tool_name=SEARCH_KNOWLEDGE_TOOL_NAME,
                    content="[1] report.md\nThe report says X.",
                    tool_call_id="call_1",
                ),
                ChatMessageText(content="The report says X."),
            ]
        )

        history = agent.get_message_history()
        self.assertEqual(len(history), 4)
        self.assertIsInstance(history[1].parts[0], ToolCallPart)
        self.assertIsInstance(history[2].parts[0], ToolReturnPart)
        self.assertEqual(history[2].parts[0].tool_call_id, "call_1")

        # The restored transcript keeps the tool turns without rendering them.
        self.assertEqual(len(conversation.chat_messages), 4)
        self.assertEqual(len(conversation.get_visible_messages()), 2)

    def test_a_restored_conversation_continues_from_its_history(self):
        """The next question is asked on top of the replayed history, not from nothing."""
        conversation, agent, scripted_model = self._build_conversation(
            StubRetriever(), turns=["never reached", "Yes, still X."]
        )
        conversation.restore_messages(
            [
                ChatUserMessageText(content="What does the report say?"),
                ChatMessageText(content="The report says X."),
            ]
        )

        messages = list(
            conversation.call_conversation(ChatUserMessageText(content="Are you sure?"))
        )

        # The model was shown the restored exchange, then the new question.
        first_request = scripted_model.messages_seen[0]
        prompts = [
            part.content
            for message in first_request
            for part in message.parts
            if isinstance(part, (UserPromptPart, TextPart))
        ]
        self.assertEqual(
            prompts, ["What does the report say?", "The report says X.", "Are you sure?"]
        )

        # The script is indexed by the number of responses the model has already given, so landing
        # on the second turn is itself proof the restored answer was part of the history.
        self.assertEqual(messages[-1].content, "Yes, still X.")

        # And the run's own turns are appended to that history rather than replacing it.
        self.assertGreaterEqual(len(agent.get_message_history()), 4)

    def test_a_failed_retrieval_becomes_an_error_message_not_a_partial_answer(self):
        """A run that broke must not leave a truncated answer looking complete."""
        retriever = StubRetriever(error=RuntimeError("LanceDB is unreachable"))
        conversation, _, _ = self._build_conversation(
            retriever, turns=[search("anything"), "Never streamed."]
        )

        messages = list(conversation.call_conversation(ChatUserMessageText(content="A question")))

        error_messages = [
            message for message in messages if isinstance(message, ChatMessageError)
        ]
        self.assertEqual(len(error_messages), 1)
        self.assertIn("LanceDB is unreachable", error_messages[0].error)

        # No answer was persisted, and nothing is left half-streamed.
        self.assertIsNone(conversation.current_response_message)
        self.assertNotIn(
            "source", [message.message_type for message in conversation.chat_messages]
        )
        self.assertNotIn("text", [message.message_type for message in conversation.chat_messages])

    def test_a_run_that_exhausted_its_retries_persists_no_answer(self):
        """The retry budget ends the run on an error, not on the text of the aborted response."""
        retriever = StubRetriever(results=[[build_chunk("chunk-1", "A passage.")]])
        # One more scripted attempt than the retry budget, so the budget is what stops the run.
        conversation, _, _ = self._build_conversation(
            retriever,
            turns=[
                ScriptedTurn(text="Still trying. ", tool_call=search("   "))
                for _ in range(KnowledgeBaseAgentAi.MAX_CONSECUTIVE_ERRORS + 2)
            ],
        )

        messages = list(conversation.call_conversation(ChatUserMessageText(content="A question")))

        error_messages = [
            message for message in messages if isinstance(message, ChatMessageError)
        ]
        self.assertEqual(len(error_messages), 1)
        self.assertIn("Maximum consecutive errors", error_messages[0].error)

        # The last response was aborted mid-turn, so its text is not persisted as an answer.
        self.assertIsNone(conversation.current_response_message)
        recorded = [message.message_type for message in conversation.chat_messages]
        self.assertEqual(recorded[-1], "error")
        self.assertNotIn("source", recorded)

    def test_a_search_that_matched_nothing_is_answered_without_sources(self):
        """An empty retrieval is an answer the model has to write, not a failure."""
        retriever = StubRetriever(results=[[]])
        conversation, _, _ = self._build_conversation(
            retriever, turns=[search("unknown"), "The documents do not cover it."]
        )

        messages = list(
            conversation.call_conversation(ChatUserMessageText(content="What about Mars?"))
        )

        final_message = messages[-1]
        self.assertIsInstance(final_message, ChatMessageText)
        self.assertNotIsInstance(final_message, ChatMessageSource)
        self.assertEqual(final_message.content, "The documents do not cover it.")

        tool_result = conversation.chat_messages[2]
        self.assertIsInstance(tool_result, ChatMessageToolResult)
        self.assertIn("No passage matched", tool_result.content)

    def test_the_sources_of_a_turn_are_what_that_turn_retrieved(self):
        """A second question must not be attributed to the passages of the first."""
        retriever = StubRetriever(
            results=[[build_chunk("chunk-1", "About X.")], [build_chunk("chunk-2", "About Y.")]]
        )
        conversation, _, _ = self._build_conversation(
            retriever,
            turns=[search("x"), "It is X.", search("y"), "It is Y."],
        )

        list(conversation.call_conversation(ChatUserMessageText(content="What about X?")))
        second = list(conversation.call_conversation(ChatUserMessageText(content="And Y?")))

        final_message = second[-1]
        self.assertIsInstance(final_message, ChatMessageSource)
        self.assertEqual([source.chunk.chunk_id for source in final_message.sources], ["chunk-2"])
