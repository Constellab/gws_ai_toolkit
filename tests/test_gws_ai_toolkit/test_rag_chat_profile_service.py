from contextlib import contextmanager

from gws_ai_toolkit.models.chat.conversation.base_chat_conversation import ChatConversationMode
from gws_ai_toolkit.models.knowledge_base.knowledge_base import KnowledgeBase
from gws_ai_toolkit.models.knowledge_base.knowledge_base_chat_config import KnowledgeBaseChatConfig
from gws_ai_toolkit.models.knowledge_base.knowledge_base_dto import SaveKnowledgeBaseDTO
from gws_ai_toolkit.models.knowledge_base.knowledge_base_service import KnowledgeBaseService
from gws_ai_toolkit.models.knowledge_base.rag_chat_profile import RagChatProfile
from gws_ai_toolkit.models.knowledge_base.rag_chat_profile_dto import (
    DEFAULT_CHAT_PROFILE_MODEL,
    DEFAULT_CHAT_PROFILE_SYSTEM_PROMPT,
    RagChatProfileDTO,
    SaveRagChatProfileDTO,
)
from gws_ai_toolkit.models.knowledge_base.rag_chat_profile_service import (
    RagChatProfileNameAlreadyUsedError,
    RagChatProfileService,
    UnknownKnowledgeBaseError,
)
from gws_ai_toolkit.models.user.user import User as LocalUser
from gws_ai_toolkit.rag.knowledge_base.knowledge_base_config import DEFAULT_TOP_K
from gws_core import BaseTestCase, CurrentUserService, StringHelper, UserGroup
from gws_core import User as GwsCoreUser
from gws_core.core.exception.exceptions.not_found_exception import NotFoundException
from gws_core.core.exception.exceptions.unauthorized_exception import UnauthorizedException


# test_rag_chat_profile_service.py
class TestRagChatProfileService(BaseTestCase):
    """Tests for the chat-profile row and its service.

    The profile's bound knowledge bases *are* the retrieval metadata filter, so most of these tests
    are about that one field: what a save accepts, and what a query-time read does with ids whose
    knowledge base has since been deleted.
    """

    service: RagChatProfileService
    knowledge_base_service: KnowledgeBaseService

    def setUp(self) -> None:
        super().setUp()
        # BaseTestCase truncates once per class, so rows from a previous test method would otherwise
        # collide with this one (profile and knowledge-base names are unique).
        RagChatProfile.delete().execute()
        KnowledgeBase.delete().execute()

        self.service = RagChatProfileService()
        self.knowledge_base_service = KnowledgeBaseService()

    ############################################### HELPERS ###############################################

    def _create_knowledge_base(self, name: str = "Protocols") -> KnowledgeBase:
        return self.knowledge_base_service.create_knowledge_base(SaveKnowledgeBaseDTO(name=name))

    def _create_profile(
        self, name: str = "Support bot", knowledge_base_ids: list[str] | None = None
    ) -> RagChatProfile:
        return self.service.create_profile(
            SaveRagChatProfileDTO(name=name, knowledge_base_ids=knowledge_base_ids or [])
        )

    def _create_admin_user(self) -> GwsCoreUser:
        return self._create_user(UserGroup.ADMIN)

    def _create_regular_user(self) -> GwsCoreUser:
        return self._create_user(UserGroup.USER)

    @staticmethod
    def _create_user(group: UserGroup) -> GwsCoreUser:
        """A gws_core user, mirrored into the brick's own local ``User`` table.

        The mirror normally happens through an async ``user.created`` event (see
        ``AiToolkitUserSyncService``), which does not run synchronously in a test. ``published_by``
        is a foreign key into that local table, so a test authenticating as a freshly created user
        must save the mirror itself rather than rely on the event.

        The email is generated rather than fixed: ``BaseTestCase`` truncates tables once per class,
        not per test method, so every test in this file sharing one hardcoded address would collide
        on the column's unique constraint from the second test onward.
        """
        email = f"{StringHelper.generate_uuid()}@gencovery.com"
        user = GwsCoreUser(email=email, first_name="Test", last_name="User", group=group).save()
        # force_insert: the mirror is built with the gws_core user's id already set, so peewee's
        # default pk-present-means-update heuristic would silently update zero rows instead of
        # inserting one.
        LocalUser.from_gws_core_user(user).save(force_insert=True)
        return user

    @contextmanager
    def _authenticated_as(self, user: GwsCoreUser):
        """Run the ``with`` block as ``user``, restoring whoever was current before.

        ``BaseTestCase`` authenticates the sysuser once for the whole test class (not per test
        method), and the test-context auth loader is a plain process-global, not something reset
        between tests. ``AuthenticateUser`` is a no-op when a user is already authenticated, so it
        cannot be used to switch here — this restores the previous user explicitly instead of
        leaving the auth context on whichever user a test last set.
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

    ############################################### CRUD ###############################################

    def test_create_profile_applies_the_defaults(self):
        profile = self._create_profile()

        self.assertIsNotNone(profile.id)
        self.assertEqual(profile.name, "Support bot")
        self.assertEqual(profile.model, DEFAULT_CHAT_PROFILE_MODEL)
        self.assertEqual(profile.top_k, DEFAULT_TOP_K)
        # Defined against the fused RRF score (~0.015-0.033), so no numeric default is safe:
        # None means "no threshold".
        self.assertIsNone(profile.score_threshold)
        self.assertEqual(profile.knowledge_base_ids, [])
        self.assertEqual(profile.system_prompt, DEFAULT_CHAT_PROFILE_SYSTEM_PROMPT)

    def test_a_new_profile_is_not_published_and_holds_no_token(self):
        """A profile created through the service is never published, and never mints a token.

        Asserted so a token cannot leak through the DTO, whatever the profile's publication state.
        """
        profile = self._create_profile()

        self.assertFalse(profile.is_published)
        self.assertIsNone(profile.publish_token)
        self.assertIsNone(profile.published_at)
        dto_json = profile.to_dto().to_json_dict()
        self.assertNotIn("publish_token", dto_json)
        self.assertFalse(dto_json["is_published"])
        self.assertIsNone(dto_json["published_at"])

    def test_default_system_prompt_instructs_tool_use_and_the_users_language(self):
        prompt = DEFAULT_CHAT_PROFILE_SYSTEM_PROMPT.lower()

        self.assertTrue(prompt.strip())
        # Substance rather than an exact string: the prompt must send the model to its retrieval tool
        # before answering, and must pin the answer to the user's own language.
        self.assertIn("search_knowledge", prompt)
        self.assertIn("tool", prompt)
        self.assertIn("language the user", prompt)

    def test_create_profile_refuses_a_duplicate_name(self):
        self._create_profile()

        with self.assertRaises(RagChatProfileNameAlreadyUsedError):
            self._create_profile()

    def test_update_profile_changes_every_editable_field(self):
        knowledge_base = self._create_knowledge_base()
        profile = self._create_profile()

        updated = self.service.update_profile(
            profile.id,
            SaveRagChatProfileDTO(
                name="Support bot v2",
                system_prompt="Answer briefly.",
                model="openai:gpt-4o",
                top_k=12,
                score_threshold=0.02,
                knowledge_base_ids=[knowledge_base.id],
            ),
        )

        self.assertEqual(updated.name, "Support bot v2")
        self.assertEqual(updated.system_prompt, "Answer briefly.")
        self.assertEqual(updated.model, "openai:gpt-4o")
        self.assertEqual(updated.top_k, 12)
        self.assertEqual(updated.score_threshold, 0.02)
        self.assertEqual(updated.knowledge_base_ids, [knowledge_base.id])

    def test_update_profile_refuses_another_profiles_name(self):
        first = self._create_profile("First")
        self._create_profile("Second")

        with self.assertRaises(RagChatProfileNameAlreadyUsedError):
            self.service.update_profile(first.id, SaveRagChatProfileDTO(name="Second"))

        # Keeping its own name is not a conflict with itself.
        renamed = self.service.update_profile(
            first.id, SaveRagChatProfileDTO(name="First", model="openai:gpt-4o")
        )
        self.assertEqual(renamed.model, "openai:gpt-4o")

    def test_get_all_profiles_is_ordered_by_name(self):
        self._create_profile("Zebra")
        self._create_profile("Alpha")

        names = [profile.name for profile in self.service.get_all_profiles()]

        self.assertEqual(names, ["Alpha", "Zebra"])

    def test_delete_profile_removes_the_row(self):
        profile = self._create_profile()

        self.service.delete_profile(profile.id)

        self.assertIsNone(self.service.get_profile(profile.id))

    ############################################### PUBLISH / UNPUBLISH ###############################################

    def test_publish_profile_mints_a_token_and_records_who(self):
        profile = self._create_profile()
        admin = self._create_admin_user()

        with self._authenticated_as(admin):
            token = self.service.publish_profile(profile.id)

        self.assertTrue(token)
        reloaded = self.service.get_profile_and_check(profile.id)
        self.assertTrue(reloaded.is_published)
        self.assertEqual(reloaded.publish_token, token)
        self.assertIsNotNone(reloaded.published_at)
        self.assertEqual(reloaded.published_by.email, admin.email)

    def test_publish_profile_never_exposes_the_token_through_the_dto(self):
        profile = self._create_profile()
        admin = self._create_admin_user()

        with self._authenticated_as(admin):
            self.service.publish_profile(profile.id)

        dto_json = self.service.get_profile_and_check(profile.id).to_dto().to_json_dict()
        self.assertNotIn("publish_token", dto_json)
        self.assertTrue(dto_json["is_published"])
        self.assertEqual(dto_json["published_by_email"], admin.email)

    def test_republishing_rotates_the_token(self):
        profile = self._create_profile()
        admin = self._create_admin_user()

        with self._authenticated_as(admin):
            first_token = self.service.publish_profile(profile.id)
            second_token = self.service.publish_profile(profile.id)

        self.assertNotEqual(first_token, second_token)
        reloaded = self.service.get_profile_and_check(profile.id)
        self.assertEqual(reloaded.publish_token, second_token)
        self.assertTrue(reloaded.is_published)

    def test_unpublish_clears_the_token_and_keeps_publish_history(self):
        profile = self._create_profile()
        admin = self._create_admin_user()

        with self._authenticated_as(admin):
            self.service.publish_profile(profile.id)
            self.service.unpublish_profile(profile.id)

        reloaded = self.service.get_profile_and_check(profile.id)
        self.assertFalse(reloaded.is_published)
        self.assertIsNone(reloaded.publish_token)
        # The last publication is kept as a record, not erased by un-publishing.
        self.assertIsNotNone(reloaded.published_at)
        self.assertEqual(reloaded.published_by.email, admin.email)

    def test_publish_profile_refuses_a_non_admin(self):
        profile = self._create_profile()
        regular_user = self._create_regular_user()

        with self._authenticated_as(regular_user), self.assertRaises(UnauthorizedException):
            self.service.publish_profile(profile.id)

        self.assertFalse(self.service.get_profile_and_check(profile.id).is_published)

    def test_publish_profile_refuses_the_sysuser(self):
        # BaseTestCase authenticates the sysuser by default: publishing must not be reachable from
        # an automated/system context any more than from a plain user.
        profile = self._create_profile()

        with self.assertRaises(UnauthorizedException):
            self.service.publish_profile(profile.id)

    def test_unpublish_profile_refuses_a_non_admin(self):
        profile = self._create_profile()
        admin = self._create_admin_user()
        regular_user = self._create_regular_user()

        with self._authenticated_as(admin):
            self.service.publish_profile(profile.id)

        with self._authenticated_as(regular_user), self.assertRaises(UnauthorizedException):
            self.service.unpublish_profile(profile.id)

        self.assertTrue(self.service.get_profile_and_check(profile.id).is_published)

    def test_publish_profile_refuses_an_unknown_profile(self):
        admin = self._create_admin_user()

        with self._authenticated_as(admin), self.assertRaises(NotFoundException):
            self.service.publish_profile("does-not-exist")

    ############################################### BOUND KNOWLEDGE BASES ###############################################

    def test_create_profile_refuses_an_unknown_knowledge_base(self):
        with self.assertRaises(UnknownKnowledgeBaseError):
            self._create_profile(knowledge_base_ids=["does-not-exist"])

        self.assertEqual(len(self.service.get_all_profiles()), 0)

    def test_update_profile_refuses_an_unknown_knowledge_base(self):
        knowledge_base = self._create_knowledge_base()
        profile = self._create_profile(knowledge_base_ids=[knowledge_base.id])

        with self.assertRaises(UnknownKnowledgeBaseError):
            self.service.update_profile(
                profile.id,
                SaveRagChatProfileDTO(
                    name=profile.name, knowledge_base_ids=[knowledge_base.id, "does-not-exist"]
                ),
            )

        # The refused save left the binding alone rather than half-applying it.
        reloaded = self.service.get_profile_and_check(profile.id)
        self.assertEqual(reloaded.knowledge_base_ids, [knowledge_base.id])

    def test_saving_the_same_knowledge_base_twice_binds_it_once(self):
        knowledge_base = self._create_knowledge_base()

        profile = self._create_profile(knowledge_base_ids=[knowledge_base.id, knowledge_base.id])

        self.assertEqual(profile.knowledge_base_ids, [knowledge_base.id])

    def test_get_valid_knowledge_base_ids_drops_dangling_ids(self):
        kept = self._create_knowledge_base("Kept")
        deleted = self._create_knowledge_base("Deleted")
        profile = self._create_profile(knowledge_base_ids=[kept.id, deleted.id])

        # The knowledge base disappears behind the profile's back: the binding is a soft
        # many-to-many with no foreign key, so nothing updated the profile.
        KnowledgeBase.delete().where(KnowledgeBase.id == deleted.id).execute()

        valid_ids = self.service.get_valid_knowledge_base_ids(profile)

        self.assertEqual(valid_ids, [kept.id])

    def test_get_valid_knowledge_base_ids_keeps_the_configured_order(self):
        first = self._create_knowledge_base("Zebra")
        second = self._create_knowledge_base("Alpha")
        profile = self._create_profile(knowledge_base_ids=[first.id, second.id])

        self.assertEqual(self.service.get_valid_knowledge_base_ids(profile), [first.id, second.id])

    def test_get_valid_knowledge_base_ids_of_an_unbound_profile_is_empty(self):
        profile = self._create_profile()

        self.assertEqual(self.service.get_valid_knowledge_base_ids(profile), [])

    ############################################### RETRIEVAL CONFIG AND DTO ###############################################

    def test_get_retrieval_config_carries_the_profiles_retrieval_settings(self):
        profile = self.service.create_profile(
            SaveRagChatProfileDTO(name="Tuned", top_k=3, score_threshold=0.02)
        )

        retrieval_config = profile.get_retrieval_config()

        self.assertEqual(retrieval_config.top_k, 3)
        self.assertEqual(retrieval_config.score_threshold, 0.02)

    def test_to_dto_carries_the_binding(self):
        knowledge_base = self._create_knowledge_base()
        profile = self._create_profile(knowledge_base_ids=[knowledge_base.id])

        dto = profile.to_dto()

        self.assertIsInstance(dto, RagChatProfileDTO)
        self.assertEqual(dto.id, profile.id)
        self.assertEqual(dto.name, profile.name)
        self.assertEqual(dto.model, profile.model)
        self.assertEqual(dto.top_k, profile.top_k)
        self.assertIsNone(dto.score_threshold)
        self.assertEqual(dto.knowledge_base_ids, [knowledge_base.id])

    ############################################### CHAT CONFIGURATION ###############################################

    def test_from_profile_carries_the_settings_a_run_needs(self):
        """A profile row becomes the value the chat loop runs on, row left behind."""
        knowledge_base = self._create_knowledge_base()
        profile = self.service.create_profile(
            SaveRagChatProfileDTO(
                name="Tuned",
                system_prompt="Search first.",
                model="openai:gpt-4.1",
                top_k=3,
                score_threshold=0.02,
                knowledge_base_ids=[knowledge_base.id],
            )
        )

        chat_config = KnowledgeBaseChatConfig.from_profile(profile)

        self.assertEqual(chat_config.chat_profile_id, profile.id)
        self.assertEqual(chat_config.system_prompt, "Search first.")
        self.assertEqual(chat_config.model, "openai:gpt-4.1")
        self.assertEqual(chat_config.top_k, 3)
        self.assertEqual(chat_config.score_threshold, 0.02)
        self.assertEqual(chat_config.knowledge_base_ids, [knowledge_base.id])

    def test_from_profile_resolves_the_binding_before_the_chat_uses_it(self):
        """The chat searches what still exists, without every caller remembering to filter."""
        kept = self._create_knowledge_base("Kept")
        deleted = self._create_knowledge_base("Deleted")
        profile = self._create_profile(knowledge_base_ids=[kept.id, deleted.id])
        KnowledgeBase.delete().where(KnowledgeBase.id == deleted.id).execute()

        chat_config = KnowledgeBaseChatConfig.from_profile(profile)

        self.assertEqual(chat_config.knowledge_base_ids, [kept.id])

    ############################################### CONVERSATION MODE ###############################################

    def test_knowledge_base_is_a_conversation_mode(self):
        self.assertEqual(ChatConversationMode.KNOWLEDGE_BASE.value, "knowledge_base")
        self.assertEqual(
            ChatConversationMode("knowledge_base"), ChatConversationMode.KNOWLEDGE_BASE
        )
        self.assertFalse(ChatConversationMode.KNOWLEDGE_BASE.is_legacy)

    def test_the_legacy_rag_mode_still_parses(self):
        # Existing rows carry mode "rag" and must stay listable in history; the value is never
        # reused by the embedded stack.
        self.assertEqual(ChatConversationMode("rag"), ChatConversationMode.RAG)
        self.assertTrue(ChatConversationMode.RAG.is_legacy)
        self.assertFalse(ChatConversationMode.AI_EXPERT.is_legacy)
