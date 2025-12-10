import os
from unittest import TestCase

from gws_ai_toolkit.models.chat.conversation.base_chat_conversation import (
    BaseChatConversationConfig,
)
from gws_ai_toolkit.models.chat.conversation.rag_chat_conversation import RagChatConversation
from gws_ai_toolkit.models.chat.message.chat_user_message import ChatUserMessageText
from gws_ai_toolkit.rag.ragflow.rag_ragflow_service import RagRagFlowService


# test_rag_chat_conversation.py
class TestRagChatConversation(TestCase):
    service: RagRagFlowService
    rag_chat_id: str = "dcd98b3e7dc911f0a2f576e267429a63"

    @classmethod
    def setUpClass(cls):
        """Set up test fixtures that are shared across all test methods."""
        cls.api_key = os.getenv("RAGFLOW_API_KEY", "")
        cls.base_url = os.getenv("RAGFLOW_BASE_URL", "")

        if not cls.api_key or not cls.base_url:
            raise OSError(
                "RAGFLOW_API_KEY and RAGFLOW_BASE_URL environment variables must be set to run these tests."
            )

        cls.rag_chat_id = os.getenv("RAGFLOW_CHAT_ID", "")
        if not cls.rag_chat_id:
            raise OSError("RAGFLOW_CHAT_ID environment variable must be set to run these tests.")

        # Initialize the service
        cls.service = RagRagFlowService(route=cls.base_url, api_key=cls.api_key)

    def test_rag_chat_conversation(self):
        rag_chat_conversation = RagChatConversation(
            BaseChatConversationConfig(chat_app_name="TestRAGChat", store_conversation_in_db=False),
            self.service,
            self.rag_chat_id,
        )

        rag_chat_conversation.create_conversation("Unit test rag chat conversation")

        events = rag_chat_conversation.call_conversation(
            ChatUserMessageText(
                content="Mouse health will be checked daily. A clinical score per the five criteria detailed in the table below will be performed at each tumor volume measurement"
            )
        )

        all_events = list(events)

        print("RAG Chat Conversation Streaming Response:")

        for event in events:
            print(event)
