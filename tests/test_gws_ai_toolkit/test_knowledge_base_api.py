"""Tests for the public chat API: ``POST /brick/gws_ai_toolkit/chat/ask``.

Two layers, matching the split between the controller and the service (see
``docs/todo/knowledge_base_public_api_plan.md`` § Verification):

- :class:`TestKnowledgeBaseApiService` drives :class:`KnowledgeBaseApiService` directly, with an
  injected :class:`KnowledgeBaseChatFactory` — the seam :class:`KnowledgeBaseChatFactory` itself
  offers for substituting a scripted model, so no API call is ever made.
- :class:`TestPublishTokenAuth` and :class:`TestKnowledgeBaseApiRateLimiter` test the HTTP boundary
  pieces in isolation.
- :class:`TestKnowledgeBaseApiController` drives the actual FastAPI route end to end through a
  ``TestClient``, with :meth:`KnowledgeBaseApiService._build_factory` patched to the same scripted
  factory — this is what proves the wire contract (status codes, header parsing, JSON field names)
  rather than just the Python-level service.
"""

import time
from contextlib import contextmanager
from unittest.mock import patch

from gws_ai_toolkit.api.knowledge_base_api_auth import INVALID_TOKEN_MESSAGE, PublishTokenAuth
from gws_ai_toolkit.api.knowledge_base_api_controller import knowledge_base_api
from gws_ai_toolkit.api.knowledge_base_api_dto import KnowledgeBaseAskRequest
from gws_ai_toolkit.api.knowledge_base_api_rate_limiter import (
    RATE_LIMIT_MESSAGE,
    KnowledgeBaseApiRateLimiter,
)
from gws_ai_toolkit.api.knowledge_base_api_service import (
    CHAT_APP_NAME,
    MAX_MESSAGE_LENGTH,
    MAX_REPLAYED_TURNS,
    UNKNOWN_SESSION_MESSAGE,
    KnowledgeBaseApiService,
)
from gws_ai_toolkit.models.chat.chat_conversation import ChatConversation
from gws_ai_toolkit.models.chat.chat_conversation_dto import SaveChatConversationDTO
from gws_ai_toolkit.models.chat.chat_conversation_service import ChatConversationService
from gws_ai_toolkit.models.chat.conversation.base_chat_conversation import ChatConversationMode
from gws_ai_toolkit.models.chat.conversation.knowledge_base_chat_conversation import (
    KnowledgeBaseChatConversation,
)
from gws_ai_toolkit.models.chat.message.chat_message_text import ChatMessageText
from gws_ai_toolkit.models.chat.message.chat_user_message import ChatUserMessageText
from gws_ai_toolkit.models.knowledge_base.knowledge_base import KnowledgeBase
from gws_ai_toolkit.models.knowledge_base.knowledge_base_agent_ai import SEARCH_KNOWLEDGE_TOOL_NAME
from gws_ai_toolkit.models.knowledge_base.knowledge_base_chat_factory import (
    KnowledgeBaseChatFactory,
)
from gws_ai_toolkit.models.knowledge_base.knowledge_base_retriever import KnowledgeBaseRetriever
from gws_ai_toolkit.models.knowledge_base.rag_chat_profile import RagChatProfile
from gws_ai_toolkit.models.knowledge_base.rag_chat_profile_dto import SaveRagChatProfileDTO
from gws_ai_toolkit.models.knowledge_base.rag_chat_profile_service import RagChatProfileService
from gws_ai_toolkit.models.user.user_sync_service import AiToolkitUserSyncService
from gws_ai_toolkit.rag.knowledge_base.knowledge_base_models import RetrievedChunk
from gws_core import BaseTestCase, CurrentUserService, StringHelper, User, UserGroup
from gws_core.core.exception.exceptions.bad_request_exception import BadRequestException
from gws_core.core.exception.exceptions.base_http_exception import BaseHTTPException
from starlette.requests import Request
from starlette.testclient import TestClient

from .agent_test_helper import SingleAgentScriptedModel, ToolCall


@contextmanager
def _authenticated_as(user: User):
    """Run the ``with`` block as ``user``, restoring whoever was current before.

    Same rationale as ``TestRagChatProfileService._authenticated_as``: ``BaseTestCase``
    authenticates the sysuser for the whole class, and ``AuthenticateUser`` is a no-op once a user
    is already authenticated, so switching users here has to restore the previous one explicitly.
    """
    previous = CurrentUserService.get_current_user()
    CurrentUserService.set_auth_user(user)
    try:
        yield
    finally:
        if previous is not None:
            CurrentUserService.set_auth_user(previous)
        else:
            CurrentUserService.clear_auth_context()


class NoopRetriever(KnowledgeBaseRetriever):
    """A retriever that is never called: most of these tests script a model that never searches."""

    def retrieve(
        self,
        query: str,
        knowledge_base_ids: list[str],
        top_k: int = 5,
        score_threshold: float | None = None,
        document_ids: list[str] | None = None,
    ) -> list[RetrievedChunk]:
        return []


class OneChunkRetriever(KnowledgeBaseRetriever):
    """Answers every search with one passage."""

    def retrieve(
        self,
        query: str,
        knowledge_base_ids: list[str],
        top_k: int = 5,
        score_threshold: float | None = None,
        document_ids: list[str] | None = None,
    ) -> list[RetrievedChunk]:
        return [
            RetrievedChunk(
                chunk_id="chunk-1",
                content="The verification budget is 42000 euros.",
                score=0.03,
                knowledge_base_id="kb-1",
                document_id="doc-1",
                filename="budget.md",
            )
        ]


def _plain_text_factory(answer: str = "Hello.") -> KnowledgeBaseChatFactory:
    """A factory whose model answers once with plain text, never searching."""
    return KnowledgeBaseChatFactory(
        chat_app_name=CHAT_APP_NAME,
        retriever=NoopRetriever(),
        model=SingleAgentScriptedModel(turns=[answer]).build(),
    )


def _searching_factory() -> KnowledgeBaseChatFactory:
    """A factory whose model always searches once, then answers from what it found."""
    return KnowledgeBaseChatFactory(
        chat_app_name=CHAT_APP_NAME,
        retriever=OneChunkRetriever(),
        model=SingleAgentScriptedModel(
            turns=[ToolCall(SEARCH_KNOWLEDGE_TOOL_NAME, {"query": "budget"}), "The budget is 42000 euros."]
        ).build(),
    )


# test_knowledge_base_api
class TestKnowledgeBaseApiService(BaseTestCase):
    """The service the route delegates to, driven directly with an injected factory."""

    @classmethod
    def init_before_test(cls):
        super().init_before_test()
        AiToolkitUserSyncService().sync_all_users()

    def setUp(self) -> None:
        super().setUp()
        RagChatProfile.delete().execute()
        KnowledgeBase.delete().execute()

        self.profile_service = RagChatProfileService()
        self.service = KnowledgeBaseApiService()

    def _create_profile(self) -> RagChatProfile:
        return self.profile_service.create_profile(SaveRagChatProfileDTO(name="Support bot"))

    def _create_conversation_row(self, mode: str, configuration: dict) -> ChatConversation:
        return ChatConversationService().save_conversation(
            SaveChatConversationDTO(
                chat_app_name=CHAT_APP_NAME, configuration=configuration, mode=mode, label="A question"
            )
        )

    ############################################### NEW CONVERSATION ###############################################

    def test_ask_creates_a_conversation_and_answers(self):
        profile = self._create_profile()

        response = self.service.ask(
            profile, KnowledgeBaseAskRequest(message="Hi there"), factory=_plain_text_factory("Hello.")
        )

        self.assertEqual(response.answer, "Hello.")
        self.assertEqual(response.references, [])
        self.assertTrue(response.session_id)

        row = ChatConversation.get_by_id_and_check(response.session_id)
        self.assertEqual(row.mode, ChatConversationMode.KNOWLEDGE_BASE.value)
        self.assertEqual(
            row.configuration[KnowledgeBaseChatConversation.CHAT_PROFILE_ID_CONFIG_KEY], profile.id
        )

    def test_ask_attributes_a_new_conversation_to_the_system_user(self):
        """External callers have no lab user; the route stamps the technical (sys)user instead."""
        profile = self._create_profile()

        response = self.service.ask(
            profile, KnowledgeBaseAskRequest(message="Hi there"), factory=_plain_text_factory()
        )

        row = ChatConversation.get_by_id_and_check(response.session_id)
        self.assertEqual(row.user.email, User.get_and_check_sysuser().email)

    def test_ask_answers_are_listable_per_profile(self):
        profile = self._create_profile()

        response = self.service.ask(
            profile, KnowledgeBaseAskRequest(message="Hi there"), factory=_plain_text_factory()
        )

        conversations = ChatConversationService().get_all_conversations_by_chat_app(CHAT_APP_NAME)
        matching = [
            conversation
            for conversation in conversations
            if conversation.configuration.get(KnowledgeBaseChatConversation.CHAT_PROFILE_ID_CONFIG_KEY)
            == profile.id
        ]
        self.assertEqual([conversation.id for conversation in matching], [response.session_id])

    def test_ask_attributes_the_answer_to_the_retrieved_sources(self):
        profile = self._create_profile()

        response = self.service.ask(
            profile, KnowledgeBaseAskRequest(message="What is the budget?"), factory=_searching_factory()
        )

        self.assertEqual(response.answer, "The budget is 42000 euros.")
        self.assertEqual([source.document_name for source in response.references], ["budget.md"])

    def test_ask_reports_a_failed_run_as_a_502_not_as_an_answer(self):
        """A truncated or missing answer must never be presented as a complete one."""
        profile = self._create_profile()
        failing_factory = KnowledgeBaseChatFactory(
            chat_app_name=CHAT_APP_NAME,
            retriever=NoopRetriever(),
            model=SingleAgentScriptedModel(turns=[]).build(),  # no scripted turn -> the run raises
        )

        with self.assertRaises(BaseHTTPException) as raised:
            self.service.ask(profile, KnowledgeBaseAskRequest(message="Hi"), factory=failing_factory)

        self.assertEqual(raised.exception.status_code, 502)

    ############################################### MESSAGE LENGTH ###############################################

    def test_ask_refuses_an_over_long_message(self):
        profile = self._create_profile()

        with self.assertRaises(BadRequestException):
            self.service.ask(
                profile,
                KnowledgeBaseAskRequest(message="x" * (MAX_MESSAGE_LENGTH + 1)),
                factory=_plain_text_factory(),
            )

    ############################################### SESSION OWNERSHIP ###############################################

    def test_ask_continues_a_conversation_it_owns(self):
        """The scripted model's turn index counts every ``ModelResponse`` in the restored history,
        so the two calls of one conversation must share one model instance — exactly how
        ``test_knowledge_base_chat_factory.py`` continues a conversation with the same factory."""
        profile = self._create_profile()
        factory = KnowledgeBaseChatFactory(
            chat_app_name=CHAT_APP_NAME,
            retriever=OneChunkRetriever(),
            model=SingleAgentScriptedModel(
                turns=[
                    ToolCall(SEARCH_KNOWLEDGE_TOOL_NAME, {"query": "budget"}),
                    "The budget is 42000 euros.",
                    "Yes, still 42000 euros.",
                ]
            ).build(),
        )

        first = self.service.ask(
            profile, KnowledgeBaseAskRequest(message="What is the budget?"), factory=factory
        )
        second = self.service.ask(
            profile,
            KnowledgeBaseAskRequest(message="Are you sure?", session_id=first.session_id),
            factory=factory,
        )

        self.assertEqual(second.session_id, first.session_id)
        self.assertEqual(second.answer, "Yes, still 42000 euros.")

    def test_ask_refuses_a_session_id_belonging_to_another_profile(self):
        owner_profile = self._create_profile()
        other_profile = self.profile_service.create_profile(SaveRagChatProfileDTO(name="Other bot"))
        row = self._create_conversation_row(
            mode=ChatConversationMode.KNOWLEDGE_BASE.value,
            configuration={KnowledgeBaseChatConversation.CHAT_PROFILE_ID_CONFIG_KEY: other_profile.id},
        )

        with self.assertRaises(BadRequestException) as raised:
            self.service.ask(
                owner_profile,
                KnowledgeBaseAskRequest(message="Hi", session_id=row.id),
                factory=_plain_text_factory(),
            )
        self.assertEqual(str(raised.exception.detail), UNKNOWN_SESSION_MESSAGE)

    def test_ask_refuses_an_unknown_session_id(self):
        profile = self._create_profile()

        with self.assertRaises(BadRequestException):
            self.service.ask(
                profile,
                KnowledgeBaseAskRequest(message="Hi", session_id="does-not-exist"),
                factory=_plain_text_factory(),
            )

    def test_ask_refuses_a_legacy_conversations_session_id(self):
        profile = self._create_profile()
        legacy_row = self._create_conversation_row(mode=ChatConversationMode.RAG.value, configuration={})

        with self.assertRaises(BadRequestException):
            self.service.ask(
                profile,
                KnowledgeBaseAskRequest(message="Hi", session_id=legacy_row.id),
                factory=_plain_text_factory(),
            )

    ############################################### REPLAYED TURNS CAP ###############################################

    def test_last_turns_keeps_only_the_trailing_user_turns(self):
        """Pure unit test of the cut: it lands on a user-message boundary, never mid tool turn."""
        messages = [
            ChatUserMessageText(content="Q1"),
            ChatMessageText(content="A1"),
            ChatUserMessageText(content="Q2"),
            ChatMessageText(content="A2"),
            ChatUserMessageText(content="Q3"),
            ChatMessageText(content="A3"),
        ]

        capped = KnowledgeBaseApiService._last_turns(messages, max_turns=2)

        self.assertEqual([message.content for message in capped], ["Q2", "A2", "Q3", "A3"])
        self.assertEqual(KnowledgeBaseApiService._last_turns(messages, max_turns=10), messages)

    def test_ask_caps_the_turns_replayed_on_restore(self):
        """A long-running conversation must not make every new question replay its whole history.

        One factory/model instance is reused for the whole growing conversation: a scripted
        ``FunctionModel``'s turn index counts every ``ModelResponse`` already in the restored
        history, so a fresh single-turn model would desync the moment a second turn is asked.
        """
        profile = self._create_profile()
        turn_count = MAX_REPLAYED_TURNS + 3
        growing_factory = KnowledgeBaseChatFactory(
            chat_app_name=CHAT_APP_NAME,
            retriever=NoopRetriever(),
            model=SingleAgentScriptedModel(turns=[f"Answer {turn}" for turn in range(turn_count)]).build(),
        )

        conversation_id = None
        for turn in range(turn_count):
            response = self.service.ask(
                profile,
                KnowledgeBaseAskRequest(message=f"Question {turn}", session_id=conversation_id),
                factory=growing_factory,
            )
            conversation_id = response.session_id

        conversation = self.service._get_or_restore_conversation(
            _plain_text_factory("unused — this call never runs the model"),
            profile,
            KnowledgeBaseAskRequest(message="One more question", session_id=conversation_id),
        )

        user_turns = [message for message in conversation.chat_messages if message.is_user_message()]
        self.assertEqual(len(user_turns), MAX_REPLAYED_TURNS)


# test_knowledge_base_api
class TestPublishTokenAuth(BaseTestCase):
    """The bearer-token dependency the route authenticates every request with."""

    @classmethod
    def init_before_test(cls):
        super().init_before_test()
        AiToolkitUserSyncService().sync_all_users()

    def setUp(self) -> None:
        super().setUp()
        RagChatProfile.delete().execute()
        self.profile_service = RagChatProfileService()

    @staticmethod
    def _request_with_header(value: str | None) -> Request:
        headers = [(b"authorization", value.encode())] if value is not None else []
        return Request(scope={"type": "http", "headers": headers})

    def _create_admin(self) -> User:
        email = f"{StringHelper.generate_uuid()}@gencovery.com"
        return User(email=email, first_name="A", last_name="B", group=UserGroup.ADMIN).save()

    def _publish_a_profile(self) -> tuple[RagChatProfile, str, User]:
        profile = self.profile_service.create_profile(SaveRagChatProfileDTO(name="Support bot"))
        admin = self._create_admin()
        with _authenticated_as(admin):
            token = self.profile_service.publish_profile(profile.id)
        return self.profile_service.get_profile_and_check(profile.id), token, admin

    def test_check_auth_resolves_the_profile_of_a_valid_token(self):
        profile, token, _admin = self._publish_a_profile()

        resolved = PublishTokenAuth.check_auth(self._request_with_header(f"Bearer {token}"))

        self.assertEqual(resolved.id, profile.id)

    def test_check_auth_rejects_a_missing_header(self):
        with self.assertRaises(BaseHTTPException) as raised:
            PublishTokenAuth.check_auth(self._request_with_header(None))
        self.assertEqual(raised.exception.detail, INVALID_TOKEN_MESSAGE)

    def test_check_auth_rejects_a_malformed_scheme(self):
        _profile, token, _admin = self._publish_a_profile()
        with self.assertRaises(BaseHTTPException) as raised:
            PublishTokenAuth.check_auth(self._request_with_header(f"Basic {token}"))
        self.assertEqual(raised.exception.detail, INVALID_TOKEN_MESSAGE)

    def test_check_auth_rejects_an_unknown_token(self):
        with self.assertRaises(BaseHTTPException) as raised:
            PublishTokenAuth.check_auth(self._request_with_header("Bearer does-not-exist"))
        self.assertEqual(raised.exception.detail, INVALID_TOKEN_MESSAGE)

    def test_check_auth_rejects_an_unpublished_profiles_former_token(self):
        profile, token, admin = self._publish_a_profile()

        with _authenticated_as(admin):
            self.profile_service.unpublish_profile(profile.id)

        with self.assertRaises(BaseHTTPException) as raised:
            PublishTokenAuth.check_auth(self._request_with_header(f"Bearer {token}"))
        self.assertEqual(raised.exception.detail, INVALID_TOKEN_MESSAGE)


# test_knowledge_base_api
class TestKnowledgeBaseApiRateLimiter(BaseTestCase):
    """The in-memory per-token cap, tested with no database involved."""

    def test_allows_up_to_the_cap_then_rejects(self):
        limiter = KnowledgeBaseApiRateLimiter(max_requests_per_window=3, window_seconds=60)

        limiter.check("token-a")
        limiter.check("token-a")
        limiter.check("token-a")
        with self.assertRaises(BaseHTTPException) as raised:
            limiter.check("token-a")

        self.assertEqual(raised.exception.status_code, 429)
        self.assertEqual(raised.exception.detail, RATE_LIMIT_MESSAGE)

    def test_tracks_each_token_independently(self):
        limiter = KnowledgeBaseApiRateLimiter(max_requests_per_window=1, window_seconds=60)

        limiter.check("token-a")
        limiter.check("token-b")  # a different token has its own budget

        with self.assertRaises(BaseHTTPException):
            limiter.check("token-a")

    def test_the_window_expires(self):
        limiter = KnowledgeBaseApiRateLimiter(max_requests_per_window=1, window_seconds=0.05)

        limiter.check("token-a")
        with self.assertRaises(BaseHTTPException):
            limiter.check("token-a")

        time.sleep(0.1)
        limiter.check("token-a")  # does not raise: the earlier hit fell out of the window


# test_knowledge_base_api
class TestKnowledgeBaseApiController(BaseTestCase):
    """End to end through the actual FastAPI route, proving the wire contract."""

    @classmethod
    def init_before_test(cls):
        super().init_before_test()
        AiToolkitUserSyncService().sync_all_users()

    def setUp(self) -> None:
        super().setUp()
        RagChatProfile.delete().execute()
        self.profile_service = RagChatProfileService()
        self.client = TestClient(knowledge_base_api)

    def _publish_a_profile(self, name: str = "Support bot") -> tuple[RagChatProfile, str]:
        profile = self.profile_service.create_profile(SaveRagChatProfileDTO(name=name))
        admin = User(
            email=f"{StringHelper.generate_uuid()}@gencovery.com",
            first_name="A",
            last_name="B",
            group=UserGroup.ADMIN,
        ).save()
        with _authenticated_as(admin):
            token = self.profile_service.publish_profile(profile.id)
        return self.profile_service.get_profile_and_check(profile.id), token

    def test_a_valid_token_answers_with_the_expected_contract(self):
        _profile, token = self._publish_a_profile()

        with patch.object(KnowledgeBaseApiService, "_build_factory", return_value=_plain_text_factory("Hello.")):
            response = self.client.post(
                "/chat/ask",
                json={"message": "Hi there"},
                headers={"Authorization": f"Bearer {token}"},
            )

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(set(body.keys()), {"answer", "session_id", "references"})
        self.assertEqual(body["answer"], "Hello.")
        self.assertEqual(body["references"], [])
        self.assertTrue(body["session_id"])

    def test_a_missing_authorization_header_is_rejected(self):
        response = self.client.post("/chat/ask", json={"message": "Hi there"})
        self.assertEqual(response.status_code, 403)

    def test_an_unknown_token_is_rejected(self):
        response = self.client.post(
            "/chat/ask", json={"message": "Hi there"}, headers={"Authorization": "Bearer does-not-exist"}
        )
        self.assertEqual(response.status_code, 403)

    def test_a_caller_supplied_profile_id_is_ignored(self):
        """No caller-supplied profile or knowledge-base id is ever accepted — the token is the scope."""
        profile, token = self._publish_a_profile()
        other_profile, _other_token = self._publish_a_profile("Other bot")

        with patch.object(KnowledgeBaseApiService, "_build_factory", return_value=_plain_text_factory()):
            response = self.client.post(
                "/chat/ask",
                json={
                    "message": "Hi there",
                    "chat_profile_id": other_profile.id,
                    "knowledge_base_id": "some-other-kb",
                },
                headers={"Authorization": f"Bearer {token}"},
            )

        self.assertEqual(response.status_code, 200)
        row = ChatConversation.get_by_id_and_check(response.json()["session_id"])
        self.assertEqual(
            row.configuration[KnowledgeBaseChatConversation.CHAT_PROFILE_ID_CONFIG_KEY], profile.id
        )

    def test_an_over_long_message_is_rejected(self):
        _profile, token = self._publish_a_profile()

        response = self.client.post(
            "/chat/ask",
            json={"message": "x" * (MAX_MESSAGE_LENGTH + 1)},
            headers={"Authorization": f"Bearer {token}"},
        )

        self.assertEqual(response.status_code, 400)

    def test_exceeding_the_request_cap_returns_429(self):
        _profile, token = self._publish_a_profile()

        with patch.object(KnowledgeBaseApiService, "_build_factory", return_value=_plain_text_factory()):
            statuses = [
                self.client.post(
                    "/chat/ask", json={"message": "Hi"}, headers={"Authorization": f"Bearer {token}"}
                ).status_code
                for _ in range(31)
            ]

        self.assertIn(429, statuses)
