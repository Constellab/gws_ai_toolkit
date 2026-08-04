"""The knowledge-base chat loop, driven end to end without an API call or a database write.

The model is a ``FunctionModel`` scripted to call ``search_knowledge`` and then answer, and the
retriever is a stub. Between them they cover what the loop actually owns: the yielded message
sequence, the scoping of a retrieval, the sources attached to the answer, the tool turns a restore
replays, and the error path.
"""

import json
from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from typing import Any

from gws_ai_toolkit.models.chat.conversation.base_chat_conversation import (
    BaseChatConversationConfig,
    ChatConversationMode,
)
from gws_ai_toolkit.models.chat.conversation.knowledge_base_chat_config import (
    KnowledgeBaseChatConfig,
)
from gws_ai_toolkit.models.chat.conversation.knowledge_base_chat_conversation import (
    SEARCH_KNOWLEDGE_TOOL_NAME,
    KnowledgeBaseChatConversation,
)
from gws_ai_toolkit.models.chat.message.chat_message_error import ChatMessageError
from gws_ai_toolkit.models.chat.message.chat_message_source import ChatMessageSource
from gws_ai_toolkit.models.chat.message.chat_message_streaming import ChatMessageStreaming
from gws_ai_toolkit.models.chat.message.chat_message_text import ChatMessageText
from gws_ai_toolkit.models.chat.message.chat_message_tool_call import ChatMessageToolCall
from gws_ai_toolkit.models.chat.message.chat_message_tool_result import ChatMessageToolResult
from gws_ai_toolkit.models.chat.message.chat_user_message import ChatUserMessageText
from gws_ai_toolkit.models.knowledge_base.knowledge_base_retriever import KnowledgeBaseRetriever
from gws_ai_toolkit.rag.knowledge_base.knowledge_base_models import RetrievedChunk
from gws_core import BaseTestCase
from pydantic_ai.messages import (
    ModelMessage,
    ModelResponse,
    TextPart,
    ToolCallPart,
    ToolReturnPart,
    UserPromptPart,
)
from pydantic_ai.models.function import AgentInfo, DeltaToolCall, FunctionModel

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
    ) -> list[RetrievedChunk]:
        self.calls.append(
            {
                "query": query,
                "knowledge_base_ids": knowledge_base_ids,
                "top_k": top_k,
                "score_threshold": score_threshold,
            }
        )
        if self.error:
            raise self.error
        if not self.results:
            return []
        index = min(len(self.calls) - 1, len(self.results) - 1)
        return self.results[index]


@dataclass
class ScriptedChatModel:
    """Scripts the turns of the knowledge-base agent.

    Attributes:
        turns: One entry per model request: a dict of tool arguments to call ``search_knowledge``
            with, or a string streamed back as text in two deltas.
        tool_names_seen: The tools the agent exposed on each request, so a test can assert that
            ``search_knowledge`` really was offered to the model.
        messages_seen: The history handed to the model on each request, so a test can assert what a
            restored conversation shows it.
    """

    turns: list[dict | str]
    tool_names_seen: list[list[str]] = field(default_factory=list)
    messages_seen: list[list[ModelMessage]] = field(default_factory=list)

    def build(self) -> FunctionModel:
        """The pydantic-ai model replaying this script."""
        return FunctionModel(stream_function=self._stream)

    async def _stream(self, messages: list[ModelMessage], info: AgentInfo) -> AsyncIterator[Any]:
        self.tool_names_seen.append(sorted(tool.name for tool in info.function_tools))
        self.messages_seen.append(list(messages))

        turn = sum(1 for message in messages if isinstance(message, ModelResponse))
        assert turn < len(self.turns), f"No scripted turn {turn} (script has {len(self.turns)})"

        answer = self.turns[turn]

        if isinstance(answer, dict):
            tool_call_id = f"call_{turn}"
            yield {
                0: DeltaToolCall(name=SEARCH_KNOWLEDGE_TOOL_NAME, tool_call_id=tool_call_id)
            }
            payload = json.dumps(answer)
            split = len(payload) // 2
            yield {0: DeltaToolCall(json_args=payload[:split], tool_call_id=tool_call_id)}
            yield {0: DeltaToolCall(json_args=payload[split:], tool_call_id=tool_call_id)}
            return

        split = max(1, len(answer) // 2)
        yield answer[:split]
        yield answer[split:]


# test_knowledge_base_chat_conversation
class TestKnowledgeBaseChatConversation(BaseTestCase):
    """The chat loop, with no API call and no database write."""

    def _build_conversation(
        self,
        retriever: StubRetriever,
        turns: list[dict | str],
        top_k: int = 5,
        score_threshold: float | None = None,
        knowledge_base_ids: list[str] | None = None,
    ) -> tuple[KnowledgeBaseChatConversation, ScriptedChatModel]:
        """A conversation driven by a scripted model, persisting nothing."""
        scripted_model = ScriptedChatModel(turns=turns)
        conversation = KnowledgeBaseChatConversation(
            config=BaseChatConversationConfig(CHAT_APP_NAME, store_conversation_in_db=False),
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
        conversation.create_conversation("A question")
        return conversation, scripted_model

    def test_a_question_streams_an_answer_and_closes_it_with_its_sources(self):
        """user → streaming* → a source message carrying what was retrieved."""
        retriever = StubRetriever(
            results=[[build_chunk("chunk-1", "The report says X."), build_chunk("chunk-2", "And Y.")]]
        )
        conversation, scripted_model = self._build_conversation(
            retriever, turns=[{"query": "report"}, "The report says X and Y."]
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

    def test_retrieval_is_scoped_to_the_profile_and_honours_its_limits(self):
        """The bound knowledge bases, top_k and the threshold all reach the retrieval."""
        retriever = StubRetriever(results=[[build_chunk("chunk-1", "A passage.")]])
        conversation, _ = self._build_conversation(
            retriever,
            turns=[{"query": "budget"}, "Here it is."],
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
        conversation, _ = self._build_conversation(
            retriever,
            turns=[{"query": "first wording"}, {"query": "second wording"}, "Both agree."],
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

    def test_the_tool_turns_are_recorded_before_the_answer_they_led_to(self):
        """A search is persisted as a call/result pair, in the order a restore replays."""
        retriever = StubRetriever(results=[[build_chunk("chunk-1", "The answer is X.")]])
        conversation, _ = self._build_conversation(
            retriever, turns=[{"query": "answer"}, "It is X."]
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

    def test_restoring_a_conversation_replays_its_tool_turns(self):
        """A restored conversation hands the model back what it already retrieved."""
        conversation, _ = self._build_conversation(StubRetriever(), turns=["Nothing to do."])

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

        history = conversation.get_message_history()
        self.assertEqual(len(history), 4)
        self.assertIsInstance(history[1].parts[0], ToolCallPart)
        self.assertIsInstance(history[2].parts[0], ToolReturnPart)
        self.assertEqual(history[2].parts[0].tool_call_id, "call_1")

        # The restored transcript keeps the tool turns without rendering them.
        self.assertEqual(len(conversation.chat_messages), 4)
        self.assertEqual(len(conversation.get_visible_messages()), 2)

    def test_a_restored_conversation_continues_from_its_history(self):
        """The next question is asked on top of the replayed history, not from nothing."""
        conversation, scripted_model = self._build_conversation(
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
        self.assertGreaterEqual(len(conversation.get_message_history()), 4)

    def test_a_failed_retrieval_becomes_an_error_message_not_a_partial_answer(self):
        """A run that broke must not leave a truncated answer looking complete."""
        retriever = StubRetriever(error=RuntimeError("LanceDB is unreachable"))
        conversation, _ = self._build_conversation(
            retriever, turns=[{"query": "anything"}, "Never streamed."]
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

    def test_a_search_that_matched_nothing_is_answered_without_sources(self):
        """An empty retrieval is an answer the model has to write, not a failure."""
        retriever = StubRetriever(results=[[]])
        conversation, _ = self._build_conversation(
            retriever, turns=[{"query": "unknown"}, "The documents do not cover it."]
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
