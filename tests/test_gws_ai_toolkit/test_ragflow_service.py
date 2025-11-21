import os
from unittest import TestCase, skipIf

from ragflow_sdk import Chat, Session

from gws_ai_toolkit.rag.ragflow.ragflow_class import (
    RagFlowCreateChatRequest, RagFlowCreateSessionRequest)
from gws_ai_toolkit.rag.ragflow.ragflow_service import RagFlowService


# test_ragflow_service.py
@skipIf(
    not os.getenv('RAGFLOW_API_KEY') or not os.getenv('RAGFLOW_BASE_URL'),
    "[RAGFLOW_API_KEY, RAGFLOW_BASE_URL] environment variables must be set to run these tests. Define them or create a .env.test file in the brick root."
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

    @classmethod
    def setUpClass(cls):
        """Set up test fixtures that are shared across all test methods."""
        cls.api_key = os.getenv('RAGFLOW_API_KEY', '')
        cls.base_url = os.getenv('RAGFLOW_BASE_URL', '')

        # Initialize the service
        cls.service = RagFlowService(base_url=cls.base_url, api_key=cls.api_key)

        # Create a test chat for session management tests
        chat_request = RagFlowCreateChatRequest(
            name="Test Chat for Session Management",
            avatar="",
            knowledgebases=[]
        )
        cls.test_chat: Chat = cls.service.create_chat(chat_request)
        cls.test_chat_id = cls.test_chat.id

    @classmethod
    def tearDownClass(cls):
        """Clean up test resources after all tests complete."""
        try:
            # Delete the test chat (this will also delete all sessions)
            cls.service.delete_chats([cls.test_chat_id])
        except Exception as e:
            print(f"Warning: Failed to clean up test chat: {e}")

    def test_create_session(self):
        """Test creating a new session in a chat."""
        # Create a session request
        session_request = RagFlowCreateSessionRequest(name="Test Session 1")

        # Create the session
        session = self.service.create_session(
            chat_id=self.test_chat_id,
            session=session_request
        )

        # Verify the session was created
        self.assertIsInstance(session, Session)
        self.assertIsNotNone(session.id)
        self.assertEqual(session.name, "Test Session 1")

        # Clean up
        self.service.delete_sessions(self.test_chat_id, [session.id])

    def test_list_sessions(self):
        """Test listing sessions in a chat."""
        # Create multiple test sessions
        session_names = ["List Test Session 1", "List Test Session 2", "List Test Session 3"]
        created_session_ids = []

        for name in session_names:
            session_request = RagFlowCreateSessionRequest(name=name)
            session = self.service.create_session(
                chat_id=self.test_chat_id,
                session=session_request
            )
            created_session_ids.append(session.id)

        # List sessions with pagination
        sessions = self.service.list_sessions(
            chat_id=self.test_chat_id,
            page=1,
            page_size=10
        )

        # Verify sessions were listed
        self.assertIsInstance(sessions, list)
        self.assertGreaterEqual(len(sessions), 3)

        # Verify all sessions are Session instances
        for session in sessions:
            self.assertIsInstance(session, Session)
            self.assertIsNotNone(session.id)
            self.assertIsNotNone(session.name)

        # Clean up
        self.service.delete_sessions(self.test_chat_id, created_session_ids)

    def test_delete_sessions(self):
        """Test deleting multiple sessions from a chat."""
        # Create sessions to delete
        session_names = ["Delete Test Session 1", "Delete Test Session 2"]
        created_session_ids = []

        for name in session_names:
            session_request = RagFlowCreateSessionRequest(name=name)
            session = self.service.create_session(
                chat_id=self.test_chat_id,
                session=session_request
            )
            created_session_ids.append(session.id)

        # Delete the sessions
        self.service.delete_sessions(self.test_chat_id, created_session_ids)

        # Verify sessions were deleted by listing remaining sessions
        remaining_sessions = self.service.list_sessions(
            chat_id=self.test_chat_id,
            page=1,
            page_size=100
        )

        remaining_session_ids = [s.id for s in remaining_sessions]

        # Verify deleted sessions are not in the list
        for session_id in created_session_ids:
            self.assertNotIn(session_id, remaining_session_ids)

    def test_get_session(self):
        """Test retrieving a specific session by ID."""
        # Create a test session
        session_request = RagFlowCreateSessionRequest(name="Get Test Session")
        created_session = self.service.create_session(
            chat_id=self.test_chat_id,
            session=session_request
        )

        # Get the session by ID
        retrieved_session = self.service.get_session(
            chat_id=self.test_chat_id,
            session_id=created_session.id
        )

        # Verify the retrieved session matches the created session
        self.assertIsInstance(retrieved_session, Session)
        self.assertEqual(retrieved_session.id, created_session.id)
        self.assertEqual(retrieved_session.name, "Get Test Session")

        # Clean up
        self.service.delete_sessions(self.test_chat_id, [created_session.id])

    def test_list_sessions_pagination(self):
        """Test session listing with pagination parameters."""
        # Create multiple sessions
        session_count = 5
        created_session_ids = []

        for i in range(session_count):
            session_request = RagFlowCreateSessionRequest(name=f"Pagination Test Session {i}")
            session = self.service.create_session(
                chat_id=self.test_chat_id,
                session=session_request
            )
            created_session_ids.append(session.id)

        # Test first page with page_size=2
        page1_sessions = self.service.list_sessions(
            chat_id=self.test_chat_id,
            page=1,
            page_size=2
        )

        # Verify we got at most 2 sessions
        self.assertLessEqual(len(page1_sessions), 2)

        # Test second page
        page2_sessions = self.service.list_sessions(
            chat_id=self.test_chat_id,
            page=2,
            page_size=2
        )

        # Verify pagination worked (pages should be different unless total is <= 2)
        if len(page1_sessions) == 2:
            page1_ids = [s.id for s in page1_sessions]
            page2_ids = [s.id for s in page2_sessions]

            # Verify no overlap between pages
            for session_id in page2_ids:
                self.assertNotIn(session_id, page1_ids)

        # Clean up
        self.service.delete_sessions(self.test_chat_id, created_session_ids)

    def test_create_session_with_invalid_chat_id(self):
        """Test creating a session with an invalid chat ID raises an error."""
        session_request = RagFlowCreateSessionRequest(name="Invalid Chat Test")

        # Try to create a session with an invalid chat ID
        with self.assertRaises(Exception):
            self.service.create_session(
                chat_id="invalid_chat_id",
                session=session_request
            )

    def test_list_sessions_empty_chat(self):
        """Test listing sessions in a chat with no sessions."""
        # Create a new empty chat
        chat_request = RagFlowCreateChatRequest(
            name="Empty Chat for Session Test",
            avatar="",
            knowledgebases=[]
        )
        empty_chat = self.service.create_chat(chat_request)

        try:
            # List sessions in the empty chat
            sessions = self.service.list_sessions(
                chat_id=empty_chat.id,
                page=1,
                page_size=10
            )

            # Verify the list is empty or contains only default sessions
            self.assertIsInstance(sessions, list)

        finally:
            # Clean up
            self.service.delete_chats([empty_chat.id])

    def test_ask_stream(self):
        """Test asking a question with streaming response."""
        # Create a test session for the question
        session_request = RagFlowCreateSessionRequest(name="Ask Stream Test Session")
        test_session = self.service.create_session(
            chat_id=self.test_chat_id,
            session=session_request
        )

        try:
            # Ask a question with streaming
            query = "What is this document about?"
            response_chunks = []

            # Collect streaming responses
            for chunk in self.service.ask_stream(
                chat_id=self.test_chat_id,
                query=query,
                session_id=test_session.id
            ):
                response_chunks.append(chunk)

                # Verify chunk structure
                self.assertIsNotNone(chunk.content)
                self.assertIn(chunk.role, ['user', 'assistant'])
                self.assertEqual(chunk.session_id, test_session.id)
                # id can be None according to the implementation
                # reference can be None or a list

            # Verify we got at least one response chunk
            self.assertGreater(len(response_chunks), 0, "Should receive at least one response chunk")

            # Verify we got assistant responses
            assistant_chunks = [c for c in response_chunks if c.role == 'assistant']
            self.assertGreater(len(assistant_chunks), 0, "Should receive at least one assistant response")

            # Verify content was streamed (assistant responses should have content)
            assistant_content = ''.join([c.content for c in assistant_chunks])
            self.assertGreater(len(assistant_content), 0, "Assistant response should have content")

        finally:
            # Clean up
            self.service.delete_sessions(self.test_chat_id, [test_session.id])

    def test_ask_stream_without_session_id(self):
        """Test asking a question without providing a session ID (should create one)."""
        # Ask a question without providing a session ID
        query = "Tell me about this dataset"
        response_chunks = []
        created_session_id = None

        try:
            # Collect streaming responses
            for chunk in self.service.ask_stream(
                chat_id=self.test_chat_id,
                query=query,
                session_id=None  # Don't provide session ID
            ):
                response_chunks.append(chunk)
                # Capture the session ID that was created
                if created_session_id is None:
                    created_session_id = chunk.session_id

            # Verify we got responses
            self.assertGreater(len(response_chunks), 0, "Should receive at least one response chunk")

            # Verify a session was created (all chunks should have the same session_id)
            self.assertIsNotNone(created_session_id, "A session should have been created")

            # Verify all chunks have the same session ID
            for chunk in response_chunks:
                self.assertEqual(chunk.session_id, created_session_id)

        finally:
            # Clean up the created session
            if created_session_id:
                try:
                    self.service.delete_sessions(self.test_chat_id, [created_session_id])
                except Exception as e:
                    print(f"Warning: Failed to clean up created session: {e}")
