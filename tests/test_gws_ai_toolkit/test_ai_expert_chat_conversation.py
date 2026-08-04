"""The AI Expert chat loop, driven end to end without an API call, a database or a vector store.

The model is a ``FunctionModel`` replaying a script, the retriever is a stub, and the snapshot is a
real file in a temp directory — so what is covered is what AI Expert actually owns after the port:
which mode sources its text from where, how a retrieval is scoped to the one document, that no tool
is offered, that the configured temperature reaches the model, and the error path.
"""

import os
import shutil
import tempfile
from dataclasses import dataclass, field
from unittest import TestCase

from gws_ai_toolkit.models.chat.conversation.ai_expert_agent_ai import (
    NO_PASSAGE_FOUND_MESSAGE,
    AiExpertAgentAi,
)
from gws_ai_toolkit.models.chat.conversation.ai_expert_chat_config import AiExpertChatConfig
from gws_ai_toolkit.models.chat.conversation.ai_expert_chat_conversation import (
    AiExpertChatConversation,
)
from gws_ai_toolkit.models.chat.conversation.ai_expert_document import AiExpertDocument
from gws_ai_toolkit.models.chat.conversation.base_chat_conversation import (
    BaseChatConversationConfig,
    ChatConversationMode,
)
from gws_ai_toolkit.models.chat.message.chat_message_error import ChatMessageError
from gws_ai_toolkit.models.chat.message.chat_message_streaming import ChatMessageStreaming
from gws_ai_toolkit.models.chat.message.chat_message_text import ChatMessageText
from gws_ai_toolkit.models.chat.message.chat_user_message import ChatUserMessageText
from gws_ai_toolkit.models.knowledge_base.knowledge_base_retriever import KnowledgeBaseRetriever
from gws_ai_toolkit.rag.knowledge_base.knowledge_base_models import RetrievedChunk
from pydantic_ai.messages import TextPart, UserPromptPart

from .agent_test_helper import ScriptedAnswer, SingleAgentScriptedModel

CHAT_APP_NAME = "test_ai_expert"
KNOWLEDGE_BASE_ID = "kb-1"
DOCUMENT_ID = "document-1"
DOCUMENT_NAME = "study_report.md"
SNAPSHOT_TEXT = "# Study report\n\nThe dose was 5 mg per day, given for six weeks.\n"


def build_chunk(chunk_id: str, content: str, score: float = 0.03) -> RetrievedChunk:
    """A retrieved passage of the conversation's document."""
    return RetrievedChunk(
        chunk_id=chunk_id,
        content=content,
        score=score,
        knowledge_base_id=KNOWLEDGE_BASE_ID,
        document_id=DOCUMENT_ID,
        filename=DOCUMENT_NAME,
    )


@dataclass
class StubRetriever(KnowledgeBaseRetriever):
    """A retriever answering from a script, recording how it was called.

    Attributes:
        results: Chunks to return, one entry per retrieval. The last entry answers any further one.
        error: Raised instead of returning, to exercise the error path.
        calls: The arguments of every retrieval, so a test can assert the scoping.
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
        """Record the retrieval, then answer it from the script (or raise the scripted error)."""
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


# test_ai_expert_chat_conversation
class TestAiExpertChatConversation(TestCase):
    """Both surviving AI Expert modes, with no API call and no database write."""

    temp_dir: str
    snapshot_path: str

    def setUp(self) -> None:
        super().setUp()
        self.temp_dir = tempfile.mkdtemp(prefix="ai_expert_test_")
        self.snapshot_path = os.path.join(self.temp_dir, DOCUMENT_NAME)
        with open(self.snapshot_path, "w", encoding="utf-8") as snapshot:
            snapshot.write(SNAPSHOT_TEXT)

    def tearDown(self) -> None:
        shutil.rmtree(self.temp_dir, ignore_errors=True)
        super().tearDown()

    ############################################### HELPERS ###############################################

    def _build_document(self, snapshot_path: str | None = None) -> AiExpertDocument:
        """The document the conversation is about, pointing at a real snapshot by default."""
        return AiExpertDocument(
            document_id=DOCUMENT_ID,
            knowledge_base_id=KNOWLEDGE_BASE_ID,
            filename=DOCUMENT_NAME,
            snapshot_path=snapshot_path or self.snapshot_path,
        )

    def _build_conversation(
        self,
        turns: list[ScriptedAnswer],
        retriever: StubRetriever | None = None,
        config: AiExpertChatConfig | None = None,
        document: AiExpertDocument | None = None,
    ) -> tuple[AiExpertChatConversation, AiExpertAgentAi, SingleAgentScriptedModel]:
        """A conversation driven by a scripted model, persisting nothing."""
        scripted_model = SingleAgentScriptedModel(turns=turns)
        agent = AiExpertAgentAi(
            chat_config=config or AiExpertChatConfig(),
            document=document or self._build_document(),
            retriever=retriever if retriever is not None else StubRetriever(),
            model=scripted_model.build(),
        )
        conversation = AiExpertChatConversation(
            config=BaseChatConversationConfig(CHAT_APP_NAME, store_conversation_in_db=False),
            expert_agent=agent,
        )
        conversation.create_conversation("A question about the document")
        return conversation, agent, scripted_model

    @staticmethod
    def _ask(conversation: AiExpertChatConversation, question: str) -> list:
        """Ask one question and collect every message the turn yielded."""
        return list(conversation.call_conversation(ChatUserMessageText(content=question)))

    def _assert_streamed_answer(self, messages: list, answer: str) -> None:
        """The user message is echoed, the answer streams, and it is closed as plain text."""
        self.assertIsInstance(messages[0], ChatUserMessageText)

        streamed = [message for message in messages if isinstance(message, ChatMessageStreaming)]
        self.assertTrue(streamed, "the answer must reach the UI as it is produced")
        self.assertEqual(streamed[-1].content, answer)

        final_message = messages[-1]
        self.assertIsInstance(final_message, ChatMessageText)
        self.assertEqual(final_message.content, answer)

    ############################################### RELEVANT CHUNKS ###############################################

    def test_relevant_chunks_retrieves_this_document_only_and_answers_from_it(self):
        """The passages of the one document reach the instructions, and nothing else does."""
        retriever = StubRetriever(
            results=[[build_chunk("chunk-1", "The dose was 5 mg."), build_chunk("chunk-2", "For six weeks.")]]
        )
        config = AiExpertChatConfig(mode="relevant_chunks", max_chunks=3)
        conversation, _, scripted_model = self._build_conversation(
            turns=["The dose was 5 mg per day for six weeks."],
            retriever=retriever,
            config=config,
        )

        messages = self._ask(conversation, "What was the dose?")

        # The retrieval is scoped to the knowledge base *and* to the single document.
        self.assertEqual(len(retriever.calls), 1)
        self.assertEqual(retriever.calls[0]["query"], "What was the dose?")
        self.assertEqual(retriever.calls[0]["knowledge_base_ids"], [KNOWLEDGE_BASE_ID])
        self.assertEqual(retriever.calls[0]["document_ids"], [DOCUMENT_ID])
        self.assertEqual(retriever.calls[0]["top_k"], 3)

        # The passages and the document name were substituted into the instructions.
        instructions = scripted_model.instructions_seen[0]
        self.assertIn(DOCUMENT_NAME, instructions)
        self.assertIn("The dose was 5 mg.", instructions)
        self.assertIn("For six weeks.", instructions)
        self.assertNotIn(config.prompt_file_placeholder, instructions)

        self._assert_streamed_answer(messages, "The dose was 5 mg per day for six weeks.")

    def test_each_question_retrieves_its_own_passages(self):
        """Instructions are rebuilt per turn, so a follow-up is answered from what matches *it*."""
        retriever = StubRetriever(
            results=[[build_chunk("chunk-1", "About the dose.")], [build_chunk("chunk-2", "About the duration.")]]
        )
        conversation, _, scripted_model = self._build_conversation(
            turns=["It was 5 mg.", "Six weeks."],
            retriever=retriever,
            config=AiExpertChatConfig(mode="relevant_chunks"),
        )

        self._ask(conversation, "What was the dose?")
        self._ask(conversation, "For how long?")

        self.assertEqual(
            [call["query"] for call in retriever.calls],
            ["What was the dose?", "For how long?"],
        )
        self.assertIn("About the dose.", scripted_model.instructions_seen[0])
        self.assertIn("About the duration.", scripted_model.instructions_seen[1])

    def test_a_question_matching_no_passage_is_answered_rather_than_failed(self):
        """An empty retrieval is an answer the model has to write, not a broken turn."""
        conversation, _, scripted_model = self._build_conversation(
            turns=["The document does not cover it."],
            retriever=StubRetriever(results=[[]]),
            config=AiExpertChatConfig(mode="relevant_chunks"),
        )

        messages = self._ask(conversation, "What about Mars?")

        self.assertIn(NO_PASSAGE_FOUND_MESSAGE, scripted_model.instructions_seen[0])
        self._assert_streamed_answer(messages, "The document does not cover it.")

    ############################################### FULL TEXT ###############################################

    def test_full_text_chunk_reads_the_snapshot_and_makes_no_engine_call(self):
        """The whole document text comes from the snapshot, with no retrieval at all."""
        retriever = StubRetriever(results=[[build_chunk("chunk-1", "Never retrieved.")]])
        conversation, _, scripted_model = self._build_conversation(
            turns=["It is a six-week study at 5 mg per day."],
            retriever=retriever,
            config=AiExpertChatConfig(mode="full_text_chunk"),
        )

        messages = self._ask(conversation, "Summarise the document")

        self.assertEqual(retriever.calls, [], "full_text_chunk must not touch the engine")

        instructions = scripted_model.instructions_seen[0]
        self.assertIn(DOCUMENT_NAME, instructions)
        # The exact snapshot text, not a reassembly of chunks.
        self.assertIn(SNAPSHOT_TEXT.strip(), instructions)

        self._assert_streamed_answer(messages, "It is a six-week study at 5 mg per day.")

    def test_full_text_chunk_is_not_capped_by_max_chunks(self):
        """``max_chunks`` is a retrieval limit, so it must not truncate the snapshot."""
        conversation, _, scripted_model = self._build_conversation(
            turns=["Read it all."],
            config=AiExpertChatConfig(mode="full_text_chunk", max_chunks=1),
        )

        self._ask(conversation, "Summarise the document")

        self.assertIn(SNAPSHOT_TEXT.strip(), scripted_model.instructions_seen[0])

    def test_a_snapshot_that_cannot_be_read_becomes_an_error_message(self):
        """A deleted snapshot ends the turn on an error naming it, not on a half answer."""
        conversation, _, _ = self._build_conversation(
            turns=["Never streamed."],
            config=AiExpertChatConfig(mode="full_text_chunk"),
            document=self._build_document(snapshot_path=os.path.join(self.temp_dir, "gone.md")),
        )

        messages = self._ask(conversation, "Summarise the document")

        error_messages = [
            message for message in messages if isinstance(message, ChatMessageError)
        ]
        self.assertEqual(len(error_messages), 1)
        self.assertIn("gone.md", error_messages[0].error)
        self.assertIsNone(conversation.current_response_message)
        self.assertNotIn("text", [message.message_type for message in conversation.chat_messages])

    ############################################### AGENT SHAPE ###############################################

    def test_no_tool_is_offered_to_the_model(self):
        """AI Expert is not a tool-calling agent: no code interpreter, no uploaded file, no search."""
        conversation, _, scripted_model = self._build_conversation(turns=["No tools here."])

        self._ask(conversation, "Any tools?")

        self.assertEqual(scripted_model.tool_names_seen, [[]])
        # And nothing tool-shaped is persisted either.
        recorded = [message.message_type for message in conversation.chat_messages]
        self.assertEqual(recorded, ["user-text", "text"])

    def test_the_configured_temperature_is_applied_as_a_model_setting(self):
        """Temperature is a pydantic-ai model setting now, not a provider call argument."""
        conversation, _, scripted_model = self._build_conversation(
            turns=["Focused answer."],
            config=AiExpertChatConfig(temperature=0.2),
        )

        self._ask(conversation, "A question")

        self.assertEqual(scripted_model.model_settings_seen[0]["temperature"], 0.2)

    def test_the_document_and_the_configuration_are_persisted_for_a_restore(self):
        """The mode is what a restore dispatches on, the document id what it restores from."""
        conversation, _, _ = self._build_conversation(
            turns=["An answer."], config=AiExpertChatConfig(mode="relevant_chunks", max_chunks=7)
        )

        self.assertEqual(conversation.mode, ChatConversationMode.AI_EXPERT.value)
        self.assertEqual(
            conversation.chat_configuration[AiExpertChatConversation.DOCUMENT_ID_CONFIG_KEY],
            DOCUMENT_ID,
        )
        self.assertEqual(conversation.chat_configuration["mode"], "relevant_chunks")
        self.assertEqual(conversation.chat_configuration["max_chunks"], 7)

    ############################################### RESTORE & ERRORS ###############################################

    def test_a_restored_conversation_continues_from_its_history(self):
        """The next question is asked on top of the replayed exchange, not from nothing."""
        conversation, agent, scripted_model = self._build_conversation(
            turns=["never reached", "Yes, still 5 mg."]
        )
        conversation.restore_messages(
            [
                ChatUserMessageText(content="What was the dose?"),
                ChatMessageText(content="It was 5 mg."),
            ]
        )

        messages = self._ask(conversation, "Are you sure?")

        first_request = scripted_model.messages_seen[0]
        prompts = [
            part.content
            for message in first_request
            for part in message.parts
            if isinstance(part, (UserPromptPart, TextPart))
        ]
        self.assertEqual(prompts, ["What was the dose?", "It was 5 mg.", "Are you sure?"])

        # The script is indexed by the number of answers already given, so landing on the second
        # turn is itself proof the restored answer was part of the history.
        self.assertEqual(messages[-1].content, "Yes, still 5 mg.")
        self.assertGreaterEqual(len(agent.get_message_history()), 4)

    def test_a_failed_retrieval_becomes_an_error_message_not_a_partial_answer(self):
        """A broken vector store must not leave a truncated answer looking complete."""
        conversation, _, _ = self._build_conversation(
            turns=["Never streamed."],
            retriever=StubRetriever(error=RuntimeError("LanceDB is unreachable")),
            config=AiExpertChatConfig(mode="relevant_chunks"),
        )

        messages = self._ask(conversation, "What was the dose?")

        error_messages = [
            message for message in messages if isinstance(message, ChatMessageError)
        ]
        self.assertEqual(len(error_messages), 1)
        self.assertIn("LanceDB is unreachable", error_messages[0].error)

        self.assertIsNone(conversation.current_response_message)
        recorded = [message.message_type for message in conversation.chat_messages]
        self.assertEqual(recorded, ["user-text", "error"])
