import unittest

from gws_ai_toolkit import (
    ChatApp,
    ChatConversation,
    ChatConversationService,
    ChatMessageCode,
    ChatMessageModel,
    ChatMessageText,
    SaveChatConversationDTO,
)
from gws_core import BaseTestCase


# test_chat_conversation_service.py
class TestChatConversationService(BaseTestCase):
    """Unit tests for ChatConversationService.

    Tests cover all public methods with basic functionality verification.
    """

    @classmethod
    def setUpClass(cls):
        """Set up test database and create tables."""
        # Initialize service
        super().setUpClass()
        cls.service = ChatConversationService()

    def setUp(self):
        """Set up test fixtures before each test."""
        # Create a test chat app
        self.test_chat_app = ChatApp()
        self.test_chat_app.name = f"Test Chat App {id(self)}"
        self.test_chat_app.save()

        # Create a test conversation
        self.test_conversation = ChatConversation()
        self.test_conversation.chat_app = self.test_chat_app
        self.test_conversation.configuration = {"model": "gpt-4"}
        self.test_conversation.mode = "test"
        self.test_conversation.label = "Test Conversation"
        self.test_conversation.save()

    def tearDown(self):
        """Clean up after each test."""
        # Delete test data - CASCADE should handle message sources
        ChatMessageModel.delete().where(ChatMessageModel.conversation == self.test_conversation).execute()
        ChatConversation.delete().where(ChatConversation.id == self.test_conversation.id).execute()
        ChatApp.delete().where(ChatApp.id == self.test_chat_app.id).execute()

    def test_save_conversation_with_text_message(self):
        """Test creating a new conversation with a text message."""
        # Prepare conversation DTO with text message
        conversation_dto = SaveChatConversationDTO(
            chat_app_name=self.test_chat_app.name,
            configuration={"model": "gpt-3.5-turbo"},
            mode="chat",
            label="New Conversation",
            messages=[ChatMessageText(role="user", content="Hello, AI!", external_id="msg_123")],
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
        self.assertEqual(messages[0].type, "text")
        self.assertEqual(messages[0].external_id, "msg_123")

        # Clean up
        ChatMessageModel.delete().where(ChatMessageModel.conversation == conversation).execute()
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
                ChatMessageText(role="user", content="Can you write a Python function?", external_id="msg_001"),
                ChatMessageCode(
                    role="assistant", code="def hello_world():\n    print('Hello, World!')", external_id="msg_002"
                ),
                ChatMessageText(role="user", content="Thank you!", external_id="msg_003"),
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
        self.assertEqual(len(messages), 3)

        # Find messages by content to avoid order dependency
        user_messages = [m for m in messages if m.role == "user"]
        assistant_messages = [m for m in messages if m.role == "assistant"]
        code_messages = [m for m in messages if m.type == "code"]

        # Verify user messages
        self.assertEqual(len(user_messages), 2)
        user_contents = {m.message for m in user_messages}
        self.assertIn("Can you write a Python function?", user_contents)
        self.assertIn("Thank you!", user_contents)

        # Verify code message
        self.assertEqual(len(code_messages), 1)
        self.assertEqual(code_messages[0].data["code"], "def hello_world():\n    print('Hello, World!')")
        self.assertEqual(code_messages[0].role, "assistant")

        # Verify assistant messages
        self.assertEqual(len(assistant_messages), 1)

        # Clean up
        ChatMessageModel.delete().where(ChatMessageModel.conversation == conversation).execute()
        conversation.delete_instance()

    def test_save_conversation_without_messages(self):
        """Test creating a conversation without any messages."""
        # Prepare conversation DTO without messages
        conversation_dto = SaveChatConversationDTO(
            chat_app_name=self.test_chat_app.name,
            configuration={"model": "gpt-4"},
            mode="chat",
            label="Empty Conversation",
            messages=[],
        )

        # Create conversation
        conversation = self.service.save_conversation(conversation_dto)

        # Verify conversation was created
        self.assertIsNotNone(conversation.id)
        self.assertEqual(conversation.label, "Empty Conversation")
        self.assertEqual(conversation.mode, "chat")

        # Verify no messages were created
        messages = list(ChatMessageModel.get_by_conversation(str(conversation.id)))
        self.assertEqual(len(messages), 0)

        # Clean up
        conversation.delete_instance()

    def test_get_conversation_folder_path(self):
        """Test getting the conversation folder path."""
        folder_path = self.test_conversation.get_conversation_folder_path()

        # Verify path contains conversation ID
        self.assertIn(str(self.test_conversation.id), folder_path)
        self.assertIn("chat_conversations", folder_path)

    def test_delete_conversation(self):
        """Test deleting a conversation with CASCADE."""
        # Create a conversation with messages
        conversation_dto = SaveChatConversationDTO(
            chat_app_name=self.test_chat_app.name,
            configuration={},
            mode="test",
            label="To Delete",
            messages=[ChatMessageText(role="user", content="Message to delete")],
        )
        conversation = self.service.save_conversation(conversation_dto)
        conversation_id = str(conversation.id)

        # Verify conversation and message exist
        self.assertIsNotNone(ChatConversation.get_by_id(conversation_id))
        messages = list(ChatMessageModel.get_by_conversation(conversation_id))
        self.assertEqual(len(messages), 1)

        # Delete conversation
        self.service.delete_conversation(conversation_id)

        # Verify conversation was deleted
        result = ChatConversation.select().where(ChatConversation.id == conversation_id).first()
        self.assertIsNone(result)

        # Verify messages were also deleted (CASCADE)
        messages = list(ChatMessageModel.select().where(ChatMessageModel.conversation == conversation_id))
        self.assertEqual(len(messages), 0)


if __name__ == "__main__":
    unittest.main()
