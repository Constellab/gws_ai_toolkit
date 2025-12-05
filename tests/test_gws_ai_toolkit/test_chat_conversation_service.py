from gws_ai_toolkit import (
    ChatMessageCode,
    ChatMessageModel,
)
from gws_ai_toolkit.models.chat.chat_app import ChatApp
from gws_ai_toolkit.models.chat.chat_conversation_dto import SaveChatConversationDTO
from gws_ai_toolkit.models.chat.chat_conversation_service import ChatConversationService
from gws_ai_toolkit.models.chat.chat_message_source_model import ChatMessageSourceModel
from gws_ai_toolkit.models.chat.message.chat_message_source import ChatMessageSource
from gws_ai_toolkit.models.chat.message.chat_user_message import ChatUserMessageText
from gws_ai_toolkit.models.user.user_sync_service import AiToolkitUserSyncService
from gws_ai_toolkit.rag.common.rag_models import RagChatSource, RagChatSourceChunk
from gws_core import BaseTestCase


# test_chat_conversation_service.py
class TestChatConversationService(BaseTestCase):
    """Unit tests for ChatConversationService.

    Tests cover all public methods with basic functionality verification.
    """

    test_chat_app: ChatApp

    @classmethod
    def init_before_test(cls):
        super().init_before_test()
        sync_service = AiToolkitUserSyncService()
        sync_service.sync_all_users()
        cls.service = ChatConversationService()

        cls.test_chat_app = ChatApp()
        cls.test_chat_app.name = "test"
        cls.test_chat_app.save()

    def test_save_conversation_with_text_message(self):
        """Test creating a new conversation with a text message."""
        # Prepare conversation DTO with text message
        conversation_dto = SaveChatConversationDTO(
            chat_app_name=self.test_chat_app.name,
            configuration={"model": "gpt-3.5-turbo"},
            mode="chat",
            label="New Conversation",
            messages=[
                ChatUserMessageText(role="user", content="Hello, AI!", external_id="msg_123")
            ],
        )

        # Create conversation
        conversation = self.service.save_conversation(conversation_dto)

        # Verify conversation was created
        self.assertIsNotNone(conversation.id)
        self.assertEqual(conversation.label, "New Conversation")
        self.assertEqual(conversation.mode, "chat")
        self.assertEqual(conversation.configuration["model"], "gpt-3.5-turbo")

        # Verify message was created
        messages = list(ChatMessageModel.get_by_conversation(str(conversation.id)))
        self.assertEqual(len(messages), 1)
        self.assertEqual(messages[0].message, "Hello, AI!")
        self.assertEqual(messages[0].role, "user")
        self.assertEqual(messages[0].type, "user-text")
        self.assertEqual(messages[0].external_id, "msg_123")

        # Clean up
        conversation.delete_instance()

    def test_save_conversation_with_multiple_messages(self):
        """Test creating a conversation with multiple messages of different types."""
        # Prepare conversation DTO with multiple messages
        conversation_dto = SaveChatConversationDTO(
            chat_app_name=self.test_chat_app.name,
            configuration={"temperature": 0.7},
            mode="coding",
            label="Multi-message Conversation",
            messages=[
                ChatUserMessageText(
                    role="user", content="Can you write a Python function?", external_id="msg_001"
                ),
                ChatMessageCode(
                    role="assistant",
                    code="def hello_world():\n    print('Hello, World!')",
                    external_id="msg_002",
                ),
            ],
        )

        # Create conversation
        conversation = self.service.save_conversation(conversation_dto)

        # Verify conversation was created
        self.assertIsNotNone(conversation.id)
        self.assertEqual(conversation.label, "Multi-message Conversation")
        self.assertEqual(conversation.mode, "coding")

        # Verify all messages were created
        messages = list(ChatMessageModel.get_by_conversation(str(conversation.id)))
        self.assertEqual(len(messages), 2)

        # Find messages by content to avoid order dependency
        user_messages = [m for m in messages if m.role == "user"]
        assistant_messages = [m for m in messages if m.role == "assistant"]
        code_messages = [m for m in messages if m.type == "code"]

        # Verify user messages
        self.assertEqual(len(user_messages), 1)
        user_contents = {m.message for m in user_messages}
        self.assertIn("Can you write a Python function?", user_contents)

        # Verify code message
        self.assertEqual(len(code_messages), 1)
        self.assertEqual(
            code_messages[0].data["code"], "def hello_world():\n    print('Hello, World!')"
        )
        self.assertEqual(code_messages[0].role, "assistant")

        # Verify assistant messages
        self.assertEqual(len(assistant_messages), 1)

        # Clean up
        conversation.delete_instance()

    def test_conversation_with_source(self):
        """Test creating a conversation with a message that has sources and verify source retrieval."""
        # Prepare conversation DTO with messages including sources
        conversation_dto = SaveChatConversationDTO(
            chat_app_name=self.test_chat_app.name,
            configuration={"temperature": 0.7},
            mode="coding",
            label="Conversation with Sources",
            messages=[
                ChatUserMessageText(
                    content="Can you write a Python function?", external_id="msg_001"
                ),
                ChatMessageSource(
                    sources=[
                        RagChatSource(
                            document_id="doc_123",
                            document_name="python_tutorial.pdf",
                            score=0.95,
                            chunks=[
                                RagChatSourceChunk(
                                    chunk_id="chunk_1",
                                    content="Python functions are defined using def keyword",
                                    score=0.95,
                                )
                            ],
                        ),
                        RagChatSource(
                            document_id="doc_456",
                            document_name="best_practices.pdf",
                            score=0.87,
                            chunks=[
                                RagChatSourceChunk(
                                    chunk_id="chunk_2",
                                    content="Always use descriptive function names",
                                    score=0.87,
                                )
                            ],
                        ),
                    ],
                    content="Here is the code you requested.",
                    external_id="msg_003",
                ),
            ],
        )

        # Save the conversation
        conversation = self.service.save_conversation(conversation_dto)

        # Verify conversation was created
        self.assertIsNotNone(conversation.id)
        self.assertEqual(conversation.label, "Conversation with Sources")

        # Verify messages were created
        messages = list(ChatMessageModel.get_by_conversation(str(conversation.id)))
        self.assertEqual(len(messages), 2)

        # Find the message with sources
        message_with_sources = next((m for m in messages if m.type == "source"), None)
        self.assertIsNotNone(message_with_sources)
        self.assertEqual(message_with_sources.message, "Here is the code you requested.")

        # Verify sources exist in ChatMessageSourceModel
        sources: list[ChatMessageSourceModel] = list(
            ChatMessageSourceModel.get_by_message(str(message_with_sources.id))
        )
        self.assertEqual(len(sources), 2)

        # Verify first source details
        doc_123_source = next((s for s in sources if s.document_id == "doc_123"), None)
        self.assertIsNotNone(doc_123_source)
        self.assertEqual(doc_123_source.document_name, "python_tutorial.pdf")
        self.assertEqual(doc_123_source.score, 0.95)
        chunks_123 = doc_123_source.get_chunks()
        self.assertEqual(len(chunks_123), 1)
        self.assertEqual(chunks_123[0].chunk_id, "chunk_1")
        self.assertEqual(chunks_123[0].content, "Python functions are defined using def keyword")
        self.assertEqual(chunks_123[0].score, 0.95)

        # Verify second source details
        doc_456_source = next((s for s in sources if s.document_id == "doc_456"), None)
        self.assertIsNotNone(doc_456_source)
        self.assertEqual(doc_456_source.document_name, "best_practices.pdf")
        self.assertEqual(doc_456_source.score, 0.87)

        # Test get_message_sources_by_chat_app method
        page_dto = self.service.get_message_sources_by_chat_app(
            chat_app_name=self.test_chat_app.name, page=0, number_of_items_per_page=20
        )

        # Verify page DTO structure
        self.assertIsNotNone(page_dto)
        self.assertGreaterEqual(len(page_dto.objects), 2)

        # Verify sources are returned as RagChatSource DTOs
        returned_sources = page_dto.objects
        document_ids = {source.document_id for source in returned_sources}
        self.assertIn("doc_123", document_ids)
        self.assertIn("doc_456", document_ids)

        # Verify source details from get_message_sources_by_chat_app
        source_123 = next((s for s in returned_sources if s.document_id == "doc_123"), None)
        self.assertIsNotNone(source_123)
        self.assertEqual(source_123.document_name, "python_tutorial.pdf")
        self.assertEqual(source_123.score, 0.95)

        # Clean up
        conversation.delete_instance()
