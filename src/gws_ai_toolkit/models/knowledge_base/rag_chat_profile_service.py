"""The chat-profile service: CRUD, plus the two halves of the soft knowledge-base binding.

``RagChatProfile.knowledge_base_ids`` is a JSON list with no foreign key, so nothing in the database
stops a knowledge base from being deleted while a profile still names it. This service is where that
gap is handled, and it is handled asymmetrically on purpose:

- **on save**, an unknown id is rejected — a typo or a stale form must not be persisted silently;
- **at query time**, an id whose knowledge base has disappeared is dropped and logged. Raising there
  would break a chat over a knowledge base that was deleted months later, and the honest behaviour is
  to search what still exists.

Mutations run inside a transaction and callers are handed rows, as in ``models/chat/``; the DTO
boundary for Reflex states is ``to_dto()`` on those rows.
"""

from gws_core import CurrentUserService, DateHelper, Logger, StringHelper

from gws_ai_toolkit.core.ai_toolkit_db_manager import AiToolkitDbManager
from gws_ai_toolkit.models.knowledge_base.knowledge_base import KnowledgeBase
from gws_ai_toolkit.models.knowledge_base.rag_chat_profile import RagChatProfile
from gws_ai_toolkit.models.knowledge_base.rag_chat_profile_dto import SaveRagChatProfileDTO
from gws_ai_toolkit.models.user.user import User


class RagChatProfileNameAlreadyUsedError(Exception):
    """Raised when a chat-profile name is already taken."""


class UnknownKnowledgeBaseError(Exception):
    """Raised when a profile is saved with a knowledge-base id that does not exist."""


class RagChatProfileService:
    """Creates and edits chat profiles, and resolves what their bindings still point at."""

    ############################################### READ ###############################################

    def get_profile(self, profile_id: str) -> RagChatProfile | None:
        """The profile with this id, or None."""
        return RagChatProfile.get_by_id(profile_id)

    def get_profile_and_check(self, profile_id: str) -> RagChatProfile:
        """The profile with this id.

        :raises NotFoundException: if there is none
        """
        return RagChatProfile.get_by_id_and_check(profile_id)

    def get_all_profiles(self) -> list[RagChatProfile]:
        """Every profile, ordered by name."""
        return list(RagChatProfile.get_all_ordered_by_name())

    ############################################### WRITE ###############################################

    @AiToolkitDbManager.transaction()
    def create_profile(self, profile_dto: SaveRagChatProfileDTO) -> RagChatProfile:
        """Create a chat profile.

        :raises RagChatProfileNameAlreadyUsedError: if the name is taken — checked here so callers
                get a message instead of a database integrity error
        :raises UnknownKnowledgeBaseError: if a bound knowledge base does not exist
        """
        self._check_name_is_free(profile_dto.name)
        self._check_knowledge_bases_exist(profile_dto.knowledge_base_ids)

        profile = RagChatProfile()
        self._apply_profile_dto(profile, profile_dto)
        profile.save()
        return profile

    @AiToolkitDbManager.transaction()
    def update_profile(self, profile_id: str, profile_dto: SaveRagChatProfileDTO) -> RagChatProfile:
        """Update a chat profile.

        Everything is validated before anything is applied, so a rejected save leaves the stored
        profile exactly as it was rather than half-updated.

        :raises NotFoundException: if the profile does not exist
        :raises RagChatProfileNameAlreadyUsedError: if the new name belongs to another profile
        :raises UnknownKnowledgeBaseError: if a bound knowledge base does not exist
        """
        profile = self.get_profile_and_check(profile_id)
        self._check_name_is_free(profile_dto.name, allowed_id=profile.id)
        self._check_knowledge_bases_exist(profile_dto.knowledge_base_ids)

        self._apply_profile_dto(profile, profile_dto)
        profile.save()
        return profile

    @AiToolkitDbManager.transaction()
    def delete_profile(self, profile_id: str) -> None:
        """Delete a chat profile.

        Conversations started from it are left alone: their ``chat_profile_id`` becomes a dangling
        reference, which the restore path reports rather than treating as a missing configuration.

        :raises NotFoundException: if the profile does not exist
        """
        profile = self.get_profile_and_check(profile_id)
        profile.delete_instance()

    ############################################### PUBLISH ###############################################

    @AiToolkitDbManager.transaction()
    def publish_profile(self, profile_id: str) -> str:
        """Publish a chat profile, minting a bearer token that scopes external access to it.

        Publishing (or re-publishing an already-published profile) always mints a fresh token,
        rotating out whatever token existed before: the old one stops authenticating the moment
        this returns, since it is no longer the value stored on the row.

        V1 has no per-document access filtering, so the bound knowledge bases become world-readable
        to anyone holding the returned token. The caller is responsible for showing that warning and
        the token itself to the admin performing this — the token is returned here once and is never
        written to a log or recoverable afterwards in cleartext.

        :raises NotFoundException: if the profile does not exist
        :raises UnauthorizedException: if the caller is not a lab admin
        :return: the newly minted token
        """
        CurrentUserService.check_is_admin()
        profile = self.get_profile_and_check(profile_id)
        current_user = CurrentUserService.get_and_check_current_user()

        token = self._generate_publish_token()
        profile.is_published = True
        profile.publish_token = token
        profile.published_at = DateHelper.now_utc()
        profile.published_by = User.from_gws_core_user(current_user)
        profile.save()

        Logger.info(
            f"Chat profile '{profile.name}' ({profile.id}) published by {current_user.email}."
        )
        return token

    @AiToolkitDbManager.transaction()
    def unpublish_profile(self, profile_id: str) -> None:
        """Un-publish a chat profile, clearing its token and revoking external access immediately.

        ``published_at``/``published_by`` are left as-is: they record the last time the profile was
        published rather than being reset to "never published".

        :raises NotFoundException: if the profile does not exist
        :raises UnauthorizedException: if the caller is not a lab admin
        """
        CurrentUserService.check_is_admin()
        profile = self.get_profile_and_check(profile_id)
        current_user = CurrentUserService.get_and_check_current_user()

        profile.is_published = False
        profile.publish_token = None
        profile.save()

        Logger.info(
            f"Chat profile '{profile.name}' ({profile.id}) unpublished by {current_user.email}."
        )

    @staticmethod
    def _generate_publish_token() -> str:
        """A fresh, unguessable bearer token, in the same shape as :class:`~gws_core.ShareLink`'s."""
        return StringHelper.generate_uuid() + "_" + str(DateHelper.now_utc_as_milliseconds())

    ############################################### BINDING ###############################################

    def get_valid_knowledge_base_ids(self, profile: RagChatProfile) -> list[str]:
        """The profile's bound knowledge bases that still exist, in the configured order.

        This is what a retrieval filters on. A dangling id is dropped and logged rather than raised: a
        knowledge base deleted after the profile was configured must not turn every question into an
        error.

        :param profile: the profile whose binding is being resolved
        :return: the subset of ``knowledge_base_ids`` backed by an existing knowledge base
        """
        configured_ids = profile.get_knowledge_base_ids()
        if not configured_ids:
            return []

        existing_ids = self._get_existing_knowledge_base_ids(configured_ids)

        dangling_ids = [
            knowledge_base_id
            for knowledge_base_id in configured_ids
            if knowledge_base_id not in existing_ids
        ]
        if dangling_ids:
            Logger.warning(
                f"Chat profile '{profile.name}' is bound to knowledge bases that no longer exist, "
                f"ignoring them: {', '.join(dangling_ids)}."
            )

        # Filtering the configured list rather than reading the query's own order keeps the order the
        # profile author chose.
        return [
            knowledge_base_id
            for knowledge_base_id in configured_ids
            if knowledge_base_id in existing_ids
        ]

    ############################################### INTERNALS ###############################################

    @staticmethod
    def _check_name_is_free(name: str, allowed_id: str | None = None) -> None:
        """Raise unless this name is available, ignoring the profile already holding it.

        Checked here rather than left to the unique index so callers get a message they can show a
        user instead of a database integrity error.

        :param name: the requested name
        :param allowed_id: profile allowed to keep the name — itself, on an update
        :raises RagChatProfileNameAlreadyUsedError: if another profile has this name
        """
        existing = RagChatProfile.get_by_name(name)
        if existing is not None and existing.id != allowed_id:
            raise RagChatProfileNameAlreadyUsedError(
                f"A chat profile named '{name}' already exists."
            )

    @classmethod
    def _check_knowledge_bases_exist(cls, knowledge_base_ids: list[str]) -> None:
        """Raise unless every bound id names an existing knowledge base.

        :raises UnknownKnowledgeBaseError: naming the ids that do not exist
        """
        if not knowledge_base_ids:
            return

        existing_ids = cls._get_existing_knowledge_base_ids(knowledge_base_ids)
        missing_ids = [
            knowledge_base_id
            for knowledge_base_id in knowledge_base_ids
            if knowledge_base_id not in existing_ids
        ]
        if missing_ids:
            raise UnknownKnowledgeBaseError(f"Unknown knowledge base(s): {', '.join(missing_ids)}.")

    @staticmethod
    def _get_existing_knowledge_base_ids(knowledge_base_ids: list[str]) -> set[str]:
        """The subset of these ids that a knowledge base exists for, in one query."""
        return {
            knowledge_base.id
            for knowledge_base in KnowledgeBase.select(KnowledgeBase.id).where(
                KnowledgeBase.id.in_(list(knowledge_base_ids))
            )
        }

    @classmethod
    def _apply_profile_dto(
        cls, profile: RagChatProfile, profile_dto: SaveRagChatProfileDTO
    ) -> None:
        """Copy the editable fields of a save DTO onto a row, without saving it.

        The publication columns are not among them: publishing is an explicit action of its own (see
        :meth:`publish_profile`), not a side effect of editing a profile.
        """
        profile.name = profile_dto.name
        profile.system_prompt = profile_dto.system_prompt
        profile.model = profile_dto.model
        profile.top_k = profile_dto.top_k
        profile.score_threshold = profile_dto.score_threshold
        profile.knowledge_base_ids = cls._deduplicate_ids(profile_dto.knowledge_base_ids)

    @staticmethod
    def _deduplicate_ids(knowledge_base_ids: list[str]) -> list[str]:
        """The bound ids without repeats, in the configured order.

        The binding is a set of knowledge bases, and it becomes a retrieval filter: a repeated id
        would show a knowledge base twice in a configuration screen and add nothing to a search.
        """
        seen: set[str] = set()
        unique_ids: list[str] = []
        for knowledge_base_id in knowledge_base_ids:
            if knowledge_base_id not in seen:
                seen.add(knowledge_base_id)
                unique_ids.append(knowledge_base_id)
        return unique_ids
