from types import SimpleNamespace
from typing import Any
from unittest import TestCase

from gws_ai_toolkit.models.chat.conversation.ai_expert_chat_config import AiExpertChatConfig
from gws_ai_toolkit.models.chat.conversation.ai_expert_chat_conversation import (
    AiExpertChatConversation,
)
from gws_ai_toolkit.models.chat.conversation.base_chat_conversation import (
    BaseChatConversationConfig,
)
from gws_ai_toolkit.models.chat.message.chat_message_streaming import ChatMessageStreaming
from gws_ai_toolkit.models.chat.message.chat_message_text import ChatMessageText
from gws_ai_toolkit.models.chat.message.chat_user_message import ChatUserMessageText

DATASET_ID = "dataset-1"
DOCUMENT_ID = "document-1"
DOCUMENT_NAME = "study_report.pdf"


class _FakeRagService:
    """Minimal RAG service returning canned chunks and recording the calls it received."""

    def __init__(self) -> None:
        self.get_document_chunks_calls: list[dict] = []
        self.retrieve_chunks_calls: list[dict] = []

    def get_document_chunks(self, **kwargs: Any) -> list[SimpleNamespace]:
        self.get_document_chunks_calls.append(kwargs)
        return [SimpleNamespace(content="chunk one"), SimpleNamespace(content="chunk two")]

    def retrieve_chunks(self, **kwargs: Any) -> list[SimpleNamespace]:
        self.retrieve_chunks_calls.append(kwargs)
        return [SimpleNamespace(content="relevant chunk")]


class _FakeStream:
    """Stand-in for the OpenAI streaming context manager."""

    def __init__(self, events: list[Any]) -> None:
        self._events = events

    def __enter__(self) -> "_FakeStream":
        return self

    def __exit__(self, *args: Any) -> None:
        return None

    def __iter__(self):
        return iter(self._events)


class _FakeResponses:
    def __init__(self) -> None:
        self.stream_kwargs: dict = {}

    def stream(self, **kwargs: Any) -> _FakeStream:
        self.stream_kwargs = kwargs
        return _FakeStream(
            [
                SimpleNamespace(
                    type="response.created", response=SimpleNamespace(id="resp_123")
                ),
                SimpleNamespace(type="response.output_text.delta", delta="Hello"),
                SimpleNamespace(type="response.output_text.delta", delta=" world"),
                SimpleNamespace(type="response.output_item.done"),
                SimpleNamespace(type="response.completed"),
            ]
        )


class _FakeOpenAIClient:
    def __init__(self) -> None:
        self.responses = _FakeResponses()


# test_ai_expert_chat_conversation.py
class TestAiExpertChatConversation(TestCase):
    """End-to-end tests of both surviving AI Expert modes, with the RAG and OpenAI calls stubbed."""

    def _build_conversation(
        self, config: AiExpertChatConfig
    ) -> tuple[AiExpertChatConversation, _FakeRagService, _FakeOpenAIClient]:
        rag_service = _FakeRagService()
        rag_app_service = SimpleNamespace(rag_service=rag_service, dataset_id=DATASET_ID)
        rag_resource = SimpleNamespace(
            resource_model=SimpleNamespace(name=DOCUMENT_NAME),
            get_document_id=lambda: DOCUMENT_ID,
            get_id=lambda: "resource-1",
        )

        conversation = AiExpertChatConversation(
            config=BaseChatConversationConfig(
                chat_app_name="TestAiExpert", store_conversation_in_db=False
            ),
            chat_config=config,
            rag_app_service=rag_app_service,  # type: ignore[arg-type]
            rag_resource=rag_resource,  # type: ignore[arg-type]
        )
        conversation.create_conversation("Unit test AI expert conversation")

        client = _FakeOpenAIClient()
        conversation._get_openai_client = lambda: client  # type: ignore[method-assign]

        return conversation, rag_service, client

    def _run(self, conversation: AiExpertChatConversation, question: str) -> list:
        return list(conversation.call_conversation(ChatUserMessageText(content=question)))

    def test_relevant_chunks_mode(self):
        config = AiExpertChatConfig(mode="relevant_chunks", max_chunks=3)
        conversation, rag_service, client = self._build_conversation(config)

        messages = self._run(conversation, "What was the dose?")

        # Only the relevant-chunk retrieval was used
        self.assertEqual(len(rag_service.retrieve_chunks_calls), 1)
        self.assertEqual(rag_service.get_document_chunks_calls, [])
        retrieve_call = rag_service.retrieve_chunks_calls[0]
        self.assertEqual(retrieve_call["dataset_id"], DATASET_ID)
        self.assertEqual(retrieve_call["query"], "What was the dose?")
        self.assertEqual(retrieve_call["top_k"], 3)
        self.assertEqual(retrieve_call["document_ids"], [DOCUMENT_ID])

        # The retrieved chunks and the document name were substituted into the instructions
        instructions = client.responses.stream_kwargs["instructions"]
        self.assertIn(DOCUMENT_NAME, instructions)
        self.assertIn("relevant chunk", instructions)
        self.assertNotIn(config.prompt_file_placeholder, instructions)

        self._assert_streamed_answer(messages)

    def test_full_text_chunk_mode(self):
        config = AiExpertChatConfig(mode="full_text_chunk", max_chunks=10)
        conversation, rag_service, client = self._build_conversation(config)

        messages = self._run(conversation, "Summarise the document")

        # Only the full-document retrieval was used
        self.assertEqual(len(rag_service.get_document_chunks_calls), 1)
        self.assertEqual(rag_service.retrieve_chunks_calls, [])
        chunks_call = rag_service.get_document_chunks_calls[0]
        self.assertEqual(chunks_call["dataset_id"], DATASET_ID)
        self.assertEqual(chunks_call["document_id"], DOCUMENT_ID)
        self.assertEqual(chunks_call["limit"], 10)

        # Every chunk and the document name were substituted into the instructions
        instructions = client.responses.stream_kwargs["instructions"]
        self.assertIn(DOCUMENT_NAME, instructions)
        self.assertIn("chunk one", instructions)
        self.assertIn("chunk two", instructions)

        self._assert_streamed_answer(messages)

    def test_no_tools_are_sent(self):
        """AI Expert is no longer a tool-calling agent: no code interpreter, no uploaded file."""
        conversation, _, client = self._build_conversation(
            AiExpertChatConfig(mode="relevant_chunks")
        )

        self._run(conversation, "Any tools?")

        self.assertNotIn("tools", client.responses.stream_kwargs)

    def test_response_id_is_chained_between_calls(self):
        conversation, _, client = self._build_conversation(
            AiExpertChatConfig(mode="relevant_chunks")
        )

        self._run(conversation, "First question")
        self.assertIsNone(client.responses.stream_kwargs["previous_response_id"])

        self._run(conversation, "Follow-up question")
        self.assertEqual(client.responses.stream_kwargs["previous_response_id"], "resp_123")

    def _assert_streamed_answer(self, messages: list) -> None:
        """Check the user message is echoed, deltas stream, and the answer is closed as text."""
        self.assertIsInstance(messages[0], ChatUserMessageText)

        streamed = [m for m in messages if isinstance(m, ChatMessageStreaming)]
        self.assertEqual([m.content for m in streamed], ["Hello", "Hello world"])

        final = messages[-1]
        self.assertIsInstance(final, ChatMessageText)
        self.assertEqual(final.content, "Hello world")
        self.assertEqual(final.external_id, "resp_123")
