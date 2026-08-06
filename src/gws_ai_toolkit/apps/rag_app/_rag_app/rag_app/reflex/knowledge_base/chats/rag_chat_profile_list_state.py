"""State of the chat-profile pages: list the profiles, configure one, chat with it.

A chat profile is what turns a pile of knowledge bases into something a user can talk to: the prompt,
the model, how many passages a search returns, the score a passage has to reach, and — the part that
does the real work — which knowledge bases are in scope. That binding *is* the retrieval filter, which
is why it is a list of checkboxes rather than a free-text field: an id nobody can mistype.

Four decisions worth naming.

**This state owns every mutation, from both pages.** Edit and delete are reachable from the list row
and from the detail header, through ``rag_chat_profile_actions``; publish, rotate and un-publish are
reachable only from the detail page's Publication section, where there is room to say what publishing
exposes before it is clicked. The handlers all live here regardless, which is why they read the
profile fresh from the service instead of from ``_profiles``: the detail page never populates that
list. It is also why they reach into :class:`RagChatProfileDetailState` — a change patches its cached
copy in place so a renamed or freshly published profile does not look stale on its own page, and a
delete redirects away from it, since there is nothing left there to show.

**Create and edit are the same dialog.** ``_editing_profile_id`` decides which of the two a save
performs, so the fields, the validation and the layout cannot drift between the form that creates a
profile and the form that changes one.

**The confirmations are controlled, not trigger-driven.** Delete's button is a menu item, and a menu
item cannot double as the trigger of another Radix primitive (same reason as
``knowledge_base_actions_menu``); publish's must not close itself, because it hands over to the token
dialog. So which dialog is open is state — ``action_dialog_profile_id`` plus ``action_dialog_action``,
read through :func:`is_action_dialog_open` — rather than a wrapped trigger.

**The service's own errors are re-raised as toasts.** ``RagChatProfileNameAlreadyUsedError`` and
``UnknownKnowledgeBaseError`` carry messages written for a user (a taken name, a knowledge base
deleted while the dialog was open), so they become ``ReflexAppException``; everything else is left to
the global handler installed by ``register_gws_reflex_app``.
"""

import asyncio
from collections.abc import AsyncGenerator

import reflex as rx
from gws_ai_toolkit.models.knowledge_base.knowledge_base_dto import KnowledgeBaseDTO
from gws_ai_toolkit.models.knowledge_base.knowledge_base_service import KnowledgeBaseService
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
from gws_ai_toolkit.rag.knowledge_base.knowledge_base_config import DEFAULT_TOP_K
from gws_reflex_main import ReflexAppException, ReflexMainState

from ..chat.knowledge_base_chat_state import (
    KNOWLEDGE_BASE_CHAT_ROUTE,
    KnowledgeBaseChatState,
)
from ..core.form_parsing import parse_optional_float, parse_positive_int
from .rag_chat_profile_detail_state import RagChatProfileDetailState
from .rag_chat_profile_row import ChatProfileRow, build_chat_profile_row

CHAT_PROFILES_ROUTE = "/kb/chats"

# Errors a chat-profile save raises that are the user's to fix, not bugs to log.
PROFILE_SAVE_ERRORS = (RagChatProfileNameAlreadyUsedError, UnknownKnowledgeBaseError)

# The three confirmations a page can open. "publish" covers rotating an already-published profile's
# token too: the two are mutually exclusive on any given profile, and the dialog picks its wording
# from ``is_published``.
ACTION_DIALOG_PUBLISH = "publish"
ACTION_DIALOG_UNPUBLISH = "unpublish"
ACTION_DIALOG_DELETE = "delete"

# How long to leave between closing the publish confirmation and opening the token dialog. Radix
# holds a scroll lock and ``pointer-events: none`` on the body for as long as a modal is mounted, and
# releases it on unmount; a modal that mounts before that cleanup runs inherits the lock and leaves
# the whole app unclickable. Long enough for the close transition to finish.
MODAL_HANDOVER_DELAY_SECONDS = 0.35


class RagChatProfileListState(rx.State):
    """The chat profiles of this lab, and the create / edit / publish / delete actions on them.

    The profiles themselves stay on a backend var: the dialog reads them server-side, and a system
    prompt is a paragraph that has no business being pushed to the browser once per profile per event.
    What the table renders is :attr:`profile_rows`. ``knowledge_bases`` does reach the browser — the
    dialog's checkbox list is built from it — and holds DTOs, never Peewee rows.
    """

    knowledge_bases: list[KnowledgeBaseDTO] = []
    is_loading: bool = False

    _profiles: list[RagChatProfileDTO] = []

    # The edit dialog. Empty ``_editing_profile_id`` means "create"; anything else means "update that
    # profile". The numeric fields are strings because that is what an ``rx.input`` produces — they
    # are parsed once, on save, where a bad value can be named.
    dialog_open: bool = False
    is_saving: bool = False
    _editing_profile_id: str = ""
    form_name: str = ""
    form_system_prompt: str = DEFAULT_CHAT_PROFILE_SYSTEM_PROMPT
    form_model: str = DEFAULT_CHAT_PROFILE_MODEL
    form_top_k: str = str(DEFAULT_TOP_K)
    form_score_threshold: str = ""
    form_knowledge_base_ids: list[str] = []

    # The profile a row action is working on, so its own row shows the spinner rather than the table.
    busy_profile_id: str = ""

    # Which confirmation is open, and on which profile. Both empty means none — see the module
    # docstring for why this is state rather than a Radix trigger.
    action_dialog_profile_id: str = ""
    action_dialog_action: str = ""

    # The just-minted token dialog. The token is shown here exactly once — it is not re-derivable
    # from the profile afterwards, so this state is the only place it ever exists in the browser.
    token_dialog_open: bool = False
    minted_token: str = ""
    minted_token_profile_name: str = ""

    ############################################### DERIVED ###############################################

    @rx.var
    def profile_rows(self) -> list[ChatProfileRow]:
        """The profiles as the table shows them, with their bindings resolved to names."""
        return [
            build_chat_profile_row(profile, self.knowledge_bases) for profile in self._profiles
        ]

    @rx.var
    def has_profiles(self) -> bool:
        """True when there is at least one profile to show."""
        return len(self._profiles) > 0

    @rx.var
    def has_knowledge_bases(self) -> bool:
        """True when there is at least one knowledge base a profile could bind.

        Worth its own var: a profile bound to nothing retrieves nothing, so the dialog says so
        instead of showing an empty checkbox list.
        """
        return len(self.knowledge_bases) > 0

    @rx.var
    def dialog_title(self) -> str:
        """Title of the dialog, which is the one place create and edit look different."""
        return "Edit chat profile" if self._editing_profile_id else "New chat profile"

    ############################################### LOAD ###############################################

    @rx.event
    async def load_page(self) -> AsyncGenerator[rx.event.EventType, None]:
        """Load the profiles and the knowledge bases they can bind. Bound to the page's ``on_load``.

        Both in one event: the dialog's checkbox list is the knowledge bases, so a page that loaded
        only the profiles would open an edit form that cannot show what the profile is bound to.
        """
        self.is_loading = True
        # A bare yield flushes the state to the browser. Without it the spinner would never appear:
        # a foreground event sends one delta, computed after the handler has already finished and
        # cleared the flag.
        yield
        try:
            main_state = await self.get_state(ReflexMainState)
            with await main_state.authenticate_user():
                self._profiles = [
                    profile.to_dto() for profile in RagChatProfileService().get_all_profiles()
                ]
                self.knowledge_bases = [
                    knowledge_base.to_dto()
                    for knowledge_base in KnowledgeBaseService().get_all_knowledge_bases()
                ]
        finally:
            self.is_loading = False

    ############################################### DIALOG ###############################################

    @rx.event
    def open_create_dialog(self) -> None:
        """Open the dialog on a blank form carrying the defaults.

        Only reachable from the list page, which loaded the knowledge bases the checkbox list needs.
        """
        self._editing_profile_id = ""
        self.form_name = ""
        self.form_system_prompt = DEFAULT_CHAT_PROFILE_SYSTEM_PROMPT
        self.form_model = DEFAULT_CHAT_PROFILE_MODEL
        self.form_top_k = str(DEFAULT_TOP_K)
        self.form_score_threshold = ""
        self.form_knowledge_base_ids = []
        self.dialog_open = True

    @rx.event
    async def open_edit_dialog(self, profile_id: str) -> None:
        """Open the dialog on an existing profile's current configuration.

        Read fresh from the service rather than from ``_profiles``: this also opens from the detail
        page's actions menu, and that page never loads the list.

        The bindings are shown exactly as stored, including an id whose knowledge base has since been
        deleted: a configuration screen has to show what was configured. Such an id simply has no
        checkbox to appear in, and re-saving the form drops it.

        :param profile_id: the profile to edit
        :raises ReflexAppException: if the profile no longer exists
        """
        main_state = await self.get_state(ReflexMainState)
        with await main_state.authenticate_user():
            profile = RagChatProfileService().get_profile(profile_id)
            if profile is None:
                raise ReflexAppException("This chat profile no longer exists. Refresh the page.")
            profile_dto = profile.to_dto()
            self.knowledge_bases = [
                knowledge_base.to_dto()
                for knowledge_base in KnowledgeBaseService().get_all_knowledge_bases()
            ]

        self._editing_profile_id = profile_dto.id
        self.form_name = profile_dto.name
        self.form_system_prompt = profile_dto.system_prompt
        self.form_model = profile_dto.model
        self.form_top_k = str(profile_dto.top_k)
        self.form_score_threshold = (
            "" if profile_dto.score_threshold is None else str(profile_dto.score_threshold)
        )
        self.form_knowledge_base_ids = list(profile_dto.knowledge_base_ids)
        self.dialog_open = True

    @rx.event
    def close_dialog(self) -> None:
        """Close the dialog, discarding whatever was typed."""
        self.dialog_open = False

    @rx.event
    def set_action_dialog_open(self, is_open: bool, action: str, profile_id: str) -> None:
        """Open or close one profile's confirmation dialog.

        Bound both to the menu item that opens it and to the dialog's own ``on_open_change``, so
        Radix's own ways of closing it — Escape, an overlay click, the Cancel or the action button —
        clear it the same way opening it set it.

        :param is_open: whether the dialog is being opened or closed
        :param action: one of :data:`ACTION_DIALOG_PUBLISH`, :data:`ACTION_DIALOG_UNPUBLISH`,
                       :data:`ACTION_DIALOG_DELETE`
        :param profile_id: the profile the dialog acts on
        """
        self.action_dialog_profile_id = profile_id if is_open else ""
        self.action_dialog_action = action if is_open else ""

    @rx.event
    def set_form_name(self, value: str) -> None:
        """Setter for the name field."""
        self.form_name = value

    @rx.event
    def set_form_system_prompt(self, value: str) -> None:
        """Setter for the system-prompt field."""
        self.form_system_prompt = value

    @rx.event
    def set_form_model(self, value: str) -> None:
        """Setter for the model field."""
        self.form_model = value

    @rx.event
    def set_form_top_k(self, value: str) -> None:
        """Setter for the top-k field."""
        self.form_top_k = value

    @rx.event
    def set_form_score_threshold(self, value: str) -> None:
        """Setter for the score-threshold field."""
        self.form_score_threshold = value

    @rx.event
    def toggle_knowledge_base(self, knowledge_base_id: str, checked: bool) -> None:
        """Bind or unbind one knowledge base, keeping the order the boxes were ticked in.

        :param knowledge_base_id: the knowledge base being bound or unbound
        :param checked: the checkbox's new state
        """
        if checked:
            if knowledge_base_id not in self.form_knowledge_base_ids:
                self.form_knowledge_base_ids = [*self.form_knowledge_base_ids, knowledge_base_id]
            return

        self.form_knowledge_base_ids = [
            bound_id for bound_id in self.form_knowledge_base_ids if bound_id != knowledge_base_id
        ]

    ############################################### SAVE ###############################################

    @rx.event
    async def save_profile(self) -> AsyncGenerator[rx.event.EventType, None]:
        """Create or update the profile the dialog is open on.

        An update patches the detail page's cached copy in place, so a profile renamed from its own
        page does not sit there showing its old configuration.

        :raises ReflexAppException: if the form is incomplete or holds a value that cannot be parsed,
                or if the service refuses the save (taken name, unknown knowledge base)
        """
        name = self.form_name.strip()
        if not name:
            raise ReflexAppException("A chat profile needs a name.")

        model = self.form_model.strip()
        if not model:
            raise ReflexAppException("A chat profile needs a model, as a 'provider:model' string.")

        save_dto = SaveRagChatProfileDTO(
            name=name,
            system_prompt=self.form_system_prompt.strip(),
            model=model,
            top_k=parse_positive_int(self.form_top_k, "Passages per search"),
            score_threshold=parse_optional_float(self.form_score_threshold, "Score threshold"),
            knowledge_base_ids=list(self.form_knowledge_base_ids),
        )

        profile_id = self._editing_profile_id
        self.is_saving = True
        # Flushed to the browser before the save runs, so the button's spinner is actually seen —
        # see ``load_page``.
        yield
        try:
            main_state = await self.get_state(ReflexMainState)
            service = RagChatProfileService()
            with await main_state.authenticate_user():
                try:
                    if profile_id:
                        saved = service.update_profile(profile_id, save_dto)
                    else:
                        saved = service.create_profile(save_dto)
                except PROFILE_SAVE_ERRORS as err:
                    # Both messages were written for a user; a toast is where they belong.
                    raise ReflexAppException(str(err)) from err
                saved_dto = saved.to_dto()
        finally:
            self.is_saving = False

        self.dialog_open = False
        await self._reload_profiles()
        if profile_id:
            await self._sync_detail_state(profile_id, saved_dto)
        yield rx.toast.success(f"Chat profile '{name}' saved.")

    ############################################### CHAT ###############################################

    @rx.event
    async def start_chat(self, profile_id: str) -> rx.event.EventType:
        """Open a blank chat on this profile.

        The chat state is set here rather than through a query parameter so the chat page loads with
        its profile already chosen — one navigation, and no URL carrying configuration that belongs on
        a row.

        :param profile_id: the profile to chat with
        """
        chat_state = await self.get_state(KnowledgeBaseChatState)
        await chat_state.start_chat_with_profile(profile_id)
        return rx.redirect(KNOWLEDGE_BASE_CHAT_ROUTE)

    ############################################### PUBLISH ###############################################

    @rx.event
    async def publish_profile(self, profile_id: str) -> AsyncGenerator[rx.event.EventType, None]:
        """Publish (or re-publish, rotating the token) a chat profile.

        Open to any authenticated user. The service mints a fresh token every time, so calling this
        on an already-published profile revokes its previous token as a side effect. The minted
        token is shown exactly once, in the dialog this opens — confirmation of the consequences
        happens in the caller, before this event fires.

        This is the one handler that hands one modal over to another, and the order is load-bearing:
        the confirmation is closed and *flushed* first, so Radix has unmounted it and released the
        body scroll lock before the token dialog mounts. Doing both in one delta leaves the app with
        ``pointer-events: none`` on the body and nothing clickable — see ``_publish_dialog`` in
        ``rag_chat_profile_detail_component``, which is why the confirm button does not close itself.

        :param profile_id: the profile to publish
        """
        self.action_dialog_profile_id = ""
        self.action_dialog_action = ""
        self.busy_profile_id = profile_id
        # Flushed before the publish runs, so the confirmation is gone and the row's own spinner is
        # seen — see ``load_page``.
        yield
        try:
            main_state = await self.get_state(ReflexMainState)
            service = RagChatProfileService()
            with await main_state.authenticate_user():
                token = service.publish_profile(profile_id)
                # Re-read rather than trusting a cached row: ``publish_profile`` returns the token,
                # and this page may never have loaded the list at all.
                published = service.get_profile_and_check(profile_id).to_dto()
        finally:
            self.busy_profile_id = ""

        await self._reload_profiles()
        await self._sync_detail_state(profile_id, published)

        # The publish itself is fast, so the confirmation may still be running its close transition.
        # Radix releases the body scroll lock on unmount, and a modal mounting before that cleanup
        # inherits the lock — so wait it out rather than race it.
        await asyncio.sleep(MODAL_HANDOVER_DELAY_SECONDS)

        self.minted_token = token
        self.minted_token_profile_name = published.name
        self.token_dialog_open = True

    @rx.event
    async def unpublish_profile(self, profile_id: str) -> AsyncGenerator[rx.event.EventType, None]:
        """Un-publish a chat profile, revoking access for anyone holding its token immediately.

        :param profile_id: the profile to un-publish
        """
        self.busy_profile_id = profile_id
        # Flushed before the un-publish runs, so the button's spinner is seen — see ``load_page``.
        yield
        try:
            main_state = await self.get_state(ReflexMainState)
            service = RagChatProfileService()
            with await main_state.authenticate_user():
                service.unpublish_profile(profile_id)
                unpublished = service.get_profile_and_check(profile_id).to_dto()
        finally:
            self.busy_profile_id = ""

        await self._reload_profiles()
        await self._sync_detail_state(profile_id, unpublished)
        yield rx.toast.success(
            f"Chat profile '{unpublished.name}' unpublished. Its previous token no longer works."
        )

    @rx.event
    def close_token_dialog(self) -> None:
        """Close the just-minted-token dialog, discarding it from the browser's state.

        The token was shown exactly once, in that dialog. Closing it does not revoke anything — the
        profile stays published — it only stops the token from being displayed again.
        """
        self.token_dialog_open = False
        self.minted_token = ""
        self.minted_token_profile_name = ""

    ############################################### DELETE ###############################################

    @rx.event
    async def delete_profile(self, profile_id: str) -> AsyncGenerator[rx.event.EventType, None]:
        """Delete a chat profile.

        Conversations started from it are left alone — their profile id becomes a dangling reference
        the restore path reports — so this deletes a configuration, not a history. If its own detail
        page is open when this runs, that page is left with nothing to show, so it is redirected away.

        Confirmation is the caller's: the button that reaches this sits behind an alert dialog.

        :param profile_id: the profile to delete
        """
        self.busy_profile_id = profile_id
        # Flushed before the delete runs, so the row's own spinner is seen — see ``load_page``.
        yield
        try:
            main_state = await self.get_state(ReflexMainState)
            service = RagChatProfileService()
            with await main_state.authenticate_user():
                name = service.get_profile_and_check(profile_id).name
                service.delete_profile(profile_id)
        finally:
            self.busy_profile_id = ""

        await self._reload_profiles()
        was_showing_deleted = await self._sync_detail_state(profile_id, None)
        yield rx.toast.success(f"Chat profile '{name}' deleted.")
        if was_showing_deleted:
            yield rx.redirect(CHAT_PROFILES_ROUTE)

    ############################################### INTERNALS ###############################################

    async def _sync_detail_state(
        self, profile_id: str, profile: RagChatProfileDTO | None
    ) -> bool:
        """Patch the detail page's cached profile after a change made from either page.

        :param profile_id: the profile that changed
        :param profile: its new state, or ``None`` when it was deleted
        :return: True if the detail page was showing that profile
        """
        detail_state = await self.get_state(RagChatProfileDetailState)
        return detail_state.apply_profile_change(profile_id, profile)

    async def _reload_profiles(self) -> None:
        """Re-read the profile list. Callable from the backend, unlike the events above."""
        main_state = await self.get_state(ReflexMainState)
        with await main_state.authenticate_user():
            self._profiles = [
                profile.to_dto() for profile in RagChatProfileService().get_all_profiles()
            ]


def is_action_dialog_open(profile_id: rx.Var[str] | str, action: str) -> rx.Var[bool]:
    """Whether the confirmation currently open is this profile's dialog for that action.

    Lives next to the two vars it reads rather than in one of the components: the confirmations are
    spread across the shared action cluster (delete) and the detail page's Publication section
    (publish, un-publish), and both have to agree on what "open" means.

    :param profile_id: the profile the dialog would act on
    :param action: one of :data:`ACTION_DIALOG_PUBLISH`, :data:`ACTION_DIALOG_UNPUBLISH`,
                   :data:`ACTION_DIALOG_DELETE`
    """
    return (RagChatProfileListState.action_dialog_profile_id == profile_id) & (
        RagChatProfileListState.action_dialog_action == action
    )
