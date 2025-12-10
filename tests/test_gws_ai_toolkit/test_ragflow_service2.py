import json
import os
from unittest import TestCase, skipIf

from gws_ai_toolkit.rag.ragflow.ragflow_class import (
    RagFlowCreateSessionRequest,
)
from gws_ai_toolkit.rag.ragflow.ragflow_service import RagFlowService


# test_ragflow_service2.py
@skipIf(
    not os.getenv("RAGFLOW_API_KEY") or not os.getenv("RAGFLOW_BASE_URL"),
    "[RAGFLOW_API_KEY, RAGFLOW_BASE_URL] environment variables must be set to run these tests. Define them or create a .env.test file in the brick root.",
)
class TestRagFlowService(TestCase):
    """Integration tests for RagFlow service session management methods.

    These tests use the real RagFlow SDK and require valid credentials.

    You can provide credentials in two ways:
    1. Set environment variables:
       - RAGFLOW_API_KEY: Your RagFlow API key
       - RAGFLOW_BASE_URL: Your RagFlow instance URL (e.g., http://localhost:9380)

    2. Create a .env.test file in the brick root (/lab/user/bricks/gws_ai_toolkit/.env.test):
       RAGFLOW_API_KEY=your-api-key
       RAGFLOW_BASE_URL=http://localhost:9380
    """

    test_chat_id = "dcd98b3e7dc911f0a2f576e267429a63"  # Example chat ID for testing
    session_id = "3a6cff0a1f6f434ca7a90d310a5abc72"

    @classmethod
    def setUpClass(cls):
        """Set up test fixtures that are shared across all test methods."""
        cls.api_key = os.getenv("RAGFLOW_API_KEY", "")
        cls.base_url = os.getenv("RAGFLOW_BASE_URL", "")

        # Initialize the service
        cls.service = RagFlowService(base_url=cls.base_url, api_key=cls.api_key)

    def test_get_session(self):
        """Test retrieving a session by ID."""
        session = self.service.get_session(chat_id=self.test_chat_id, session_id=self.session_id)

        # Verify session details
        self.assertIsNotNone(session)
        self.assertEqual(session.id, self.session_id)
        # self.assertEqual(session.name, "Test Session")
        self.assertEqual(session.chat_id, self.test_chat_id)

        session_messages = session.messages
        file = "/lab/user/conversation2.json"
        json.dump(session_messages, open(file, "w"))
        self.assertIsInstance(session_messages, list)

    def test_ask_stream(self):
        """Test asking a question with streaming response."""
        return
        # Create a test session for the question
        session_request = RagFlowCreateSessionRequest(name="Ask Stream Test Session")
        test_session = self.service.create_session(
            chat_id=self.test_chat_id, session=session_request
        )

        # Ask a question with streaming
        query = "Mouse health will be checked daily. A clinical score per the five criteria detailed in the table below will be performed at each tumor volume measurement?"
        response_chunks = []

        # Collect streaming responses
        for chunk in self.service.ask_stream(
            chat_id=self.test_chat_id, query=query, session_id=test_session.id
        ):
            response_chunks.append(chunk)

            # Verify chunk structure
            self.assertIsNotNone(chunk.content)
            self.assertIn(chunk.role, ["user", "assistant"])
            self.assertEqual(chunk.session_id, test_session.id)
            # id can be None according to the implementation
            # reference can be None or a list

        # Verify we got at least one response chunk
        self.assertGreater(len(response_chunks), 0, "Should receive at least one response chunk")

        # Verify we got assistant responses
        assistant_chunks = [c for c in response_chunks if c.role == "assistant"]
        self.assertGreater(
            len(assistant_chunks), 0, "Should receive at least one assistant response"
        )

        # Verify content was streamed (assistant responses should have content)
        assistant_content = "".join([c.content for c in assistant_chunks])
        self.assertGreater(len(assistant_content), 0, "Assistant response should have content")
