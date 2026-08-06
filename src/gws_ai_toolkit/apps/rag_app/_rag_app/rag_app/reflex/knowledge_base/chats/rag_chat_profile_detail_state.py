"""State of one chat profile's page: everything it is configured with, read-only.

This state reads; it never writes. Every mutation — edit, publish, rotate, un-publish, delete — stays
on :class:`~.rag_chat_profile_list_state.RagChatProfileListState`, which owns the dialogs the shared
action cluster opens, exactly as ``KnowledgeBaseListState`` drives the knowledge-base detail page. The
two pages therefore cannot drift, and there is a single owner for the token that is shown exactly
once.

The consequence runs the other way too: that state reaches back into this one through
:meth:`apply_profile_change` after a save, a publish or a delete, so a profile renamed or published
from its own page does not sit there looking stale.

Unlike the list, this state keeps its profile on a *frontend* var. The list deliberately does not — a
system prompt is a paragraph that has no business being pushed to the browser once per profile per
event — but here there is one profile and the prompt is the page's main content.
"""

import reflex as rx
from gws_ai_toolkit.models.knowledge_base.knowledge_base_dto import KnowledgeBaseDTO
from gws_ai_toolkit.models.knowledge_base.knowledge_base_service import KnowledgeBaseService
from gws_ai_toolkit.models.knowledge_base.rag_chat_profile_dto import RagChatProfileDTO
from gws_ai_toolkit.models.knowledge_base.rag_chat_profile_service import RagChatProfileService
from gws_reflex_main import ReflexMainState

from .rag_chat_profile_row import (
    ChatProfileRow,
    build_chat_profile_row,
    empty_chat_profile_row,
)

# Name of the dynamic segment of ``/kb/chats/[chat_profile_id]``. Reflex exposes it as a var of the
# same name on every state, which is also why no state here may declare a var called this.
CHAT_PROFILE_ID_ROUTE_ARG = "chat_profile_id"


class RagChatProfileDetailState(rx.State):
    """One chat profile, resolved against the knowledge bases that still exist.

    ``knowledge_bases`` holds every knowledge base of the lab rather than only the bound ones: the
    page shows what is bound *and* says how many bindings point at something deleted, and the second
    cannot be told from the first without the full set.
    """

    profile: RagChatProfileDTO | None = None
    knowledge_bases: list[KnowledgeBaseDTO] = []
    is_loading: bool = False

    ############################################### DERIVED ###############################################

    @rx.var
    def profile_row(self) -> ChatProfileRow:
        """The loaded profile as the shared action cluster and the sections take it."""
        if self.profile is None:
            return empty_chat_profile_row()
        return build_chat_profile_row(self.profile, self.knowledge_bases)

    @rx.var
    def bound_knowledge_bases(self) -> list[KnowledgeBaseDTO]:
        """The bound knowledge bases that still exist, in bound order.

        Full DTOs rather than the names the table settles for: each one is a link to its own page,
        and a link needs the id.
        """
        if self.profile is None:
            return []
        by_id = {knowledge_base.id: knowledge_base for knowledge_base in self.knowledge_bases}
        return [
            by_id[bound_id] for bound_id in self.profile.knowledge_base_ids if bound_id in by_id
        ]

    @rx.var
    def dangling_binding_count(self) -> int:
        """How many bound ids point at a knowledge base that no longer exists.

        Counted rather than merely flagged: "2 of the 5 bound knowledge bases were deleted" is the
        page's answer to a chat that suddenly retrieves less than it used to.
        """
        if self.profile is None:
            return 0
        existing = {knowledge_base.id for knowledge_base in self.knowledge_bases}
        return sum(
            1 for bound_id in self.profile.knowledge_base_ids if bound_id not in existing
        )

    @rx.var
    def threshold_explanation(self) -> str:
        """What this profile's score threshold does to a search, in one line."""
        if self.profile is None or self.profile.score_threshold is None:
            return "Every passage a search returns is kept, whatever its score."
        return (
            f"A passage scoring below {self.profile.score_threshold} is dropped, even when the "
            "search returned it."
        )

    ############################################### LOAD ###############################################

    @rx.event
    async def load_profile(self) -> None:
        """Load the profile named by the route, and the knowledge bases to resolve it against.

        Bound to the page's ``on_load``. A route naming a profile that does not exist leaves
        ``profile`` at ``None`` rather than raising: the page says so itself, and a toast on top of a
        not-found page would say it twice.
        """
        profile_id = self._get_route_profile_id()
        if not profile_id:
            self.profile = None
            self.knowledge_bases = []
            return

        self.is_loading = True
        try:
            main_state = await self.get_state(ReflexMainState)
            with await main_state.authenticate_user():
                profile = RagChatProfileService().get_profile(profile_id)
                self.profile = None if profile is None else profile.to_dto()
                self.knowledge_bases = [
                    knowledge_base.to_dto()
                    for knowledge_base in KnowledgeBaseService().get_all_knowledge_bases()
                ]
        finally:
            self.is_loading = False

    ############################################### SYNC ###############################################

    def apply_profile_change(self, profile_id: str, profile: RagChatProfileDTO | None) -> bool:
        """Patch the loaded profile after another state changed it, if it is the one on screen.

        Not an event: the caller is :class:`RagChatProfileListState`, which reaches this from the
        backend after a save, a publish or a delete. Reporting whether this page was showing that
        profile is what lets a delete decide to redirect away from a page with nothing left on it.

        :param profile_id: the profile that changed
        :param profile: its new state, or ``None`` when it was deleted
        :return: True if this page was showing that profile
        """
        if self.profile is None or self.profile.id != profile_id:
            return False
        self.profile = profile
        return True

    ############################################### INTERNALS ###############################################

    def _get_route_profile_id(self) -> str:
        """The profile id from ``/kb/chats/[chat_profile_id]``.

        Read through ``getattr``: the var is created by Reflex when the route is registered, not
        declared on this class, so a direct attribute access would be a lie to the reader.
        """
        return str(getattr(self, CHAT_PROFILE_ID_ROUTE_ARG, "") or "")
