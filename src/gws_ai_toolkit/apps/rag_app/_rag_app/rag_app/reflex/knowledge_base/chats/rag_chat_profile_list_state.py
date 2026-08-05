"""State of the chat-profile page: list the profiles, configure one, chat with it.

A chat profile is what turns a pile of knowledge bases into something a user can talk to: the prompt,
the model, how many passages a search returns, the score a passage has to reach, and — the part that
does the real work — which knowledge bases are in scope. That binding *is* the retrieval filter, which
is why it is a list of checkboxes rather than a free-text field: an id nobody can mistype.

Two decisions worth naming.

**Create and edit are the same dialog.** ``_editing_profile_id`` decides which of the two a save
performs, so the fields, the validation and the layout cannot drift between the form that creates a
profile and the form that changes one.

**The service's own errors are re-raised as toasts.** ``RagChatProfileNameAlreadyUsedError`` and
``UnknownKnowledgeBaseError`` carry messages written for a user (a taken name, a knowledge base
deleted while the dialog was open), so they become ``ReflexAppException``; everything else is left to
the global handler installed by ``register_gws_reflex_app``.
"""

from collections.abc import AsyncGenerator
from dataclasses import dataclass, field

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

CHAT_PROFILES_ROUTE = "/kb/chats"

# Errors a chat-profile save raises that are the user's to fix, not bugs to log.
PROFILE_SAVE_ERRORS = (RagChatProfileNameAlreadyUsedError, UnknownKnowledgeBaseError)

# What the table shows for a profile that set no score threshold, which is the default and not a
# missing value.
NO_THRESHOLD_LABEL = "—"


@dataclass
class ChatProfileRow:
    """One row of the profile table, resolved server-side.

    The table needs the *names* of the bound knowledge bases, which the profile only holds ids for, so
    the join happens here rather than in the browser. Two facts are carried rather than left to be
    inferred from an empty list, because they mean different things: a profile bound to nothing
    retrieves nothing, and a profile bound to a knowledge base that has since been deleted searches
    less than its author configured.

    Attributes:
        id: The profile's id.
        name: The profile's name.
        model: Its ``provider:model`` string.
        top_k_label: How many passages one search returns.
        threshold_label: The score a passage must reach, or :data:`NO_THRESHOLD_LABEL`.
        knowledge_base_names: Names of the bound knowledge bases that still exist, in bound order.
        is_unbound: True when the profile binds no knowledge base at all.
        has_dangling_bindings: True when it binds an id whose knowledge base no longer exists.
        is_published: True when this profile's bound knowledge bases are reachable through a
            publish token by anyone holding it.
        published_label: Human-readable "since when, by whom" for a published profile, empty
            otherwise.
    """

    id: str
    name: str
    model: str
    top_k_label: str
    threshold_label: str
    knowledge_base_names: list[str] = field(default_factory=list)
    is_unbound: bool = False
    has_dangling_bindings: bool = False
    is_published: bool = False
    published_label: str = ""


class RagChatProfileListState(rx.State):
    """The chat profiles of this lab, and the create / edit / delete actions on them.

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

    # The just-minted token dialog. The token is shown here exactly once — it is not re-derivable
    # from the profile afterwards, so this state is the only place it ever exists in the browser.
    token_dialog_open: bool = False
    minted_token: str = ""
    minted_token_profile_name: str = ""

    ############################################### DERIVED ###############################################

    @rx.var
    async def is_admin(self) -> bool:
        """Whether the current user may publish or un-publish a profile.

        Publishing exposes a lab's knowledge bases to anyone holding the token, so the action is
        admin-only. The service enforces this too — this var only decides whether the button shows.
        """
        main_state = await self.get_state(ReflexMainState)
        user = await main_state.get_current_user()
        return user is not None and user.is_admin

    @rx.var
    def profile_rows(self) -> list[ChatProfileRow]:
        """The profiles as the table shows them, with their bindings resolved to names."""
        names_by_id = {
            knowledge_base.id: knowledge_base.name for knowledge_base in self.knowledge_bases
        }
        return [
            ChatProfileRow(
                id=profile.id,
                name=profile.name,
                model=profile.model,
                top_k_label=str(profile.top_k),
                threshold_label=(
                    NO_THRESHOLD_LABEL
                    if profile.score_threshold is None
                    else str(profile.score_threshold)
                ),
                knowledge_base_names=[
                    names_by_id[bound_id]
                    for bound_id in profile.knowledge_base_ids
                    if bound_id in names_by_id
                ],
                is_unbound=not profile.knowledge_base_ids,
                has_dangling_bindings=any(
                    bound_id not in names_by_id for bound_id in profile.knowledge_base_ids
                ),
                is_published=profile.is_published,
                published_label=self._published_label(profile),
            )
            for profile in self._profiles
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
        """Open the dialog on a blank form carrying the defaults."""
        self._editing_profile_id = ""
        self.form_name = ""
        self.form_system_prompt = DEFAULT_CHAT_PROFILE_SYSTEM_PROMPT
        self.form_model = DEFAULT_CHAT_PROFILE_MODEL
        self.form_top_k = str(DEFAULT_TOP_K)
        self.form_score_threshold = ""
        self.form_knowledge_base_ids = []
        self.dialog_open = True

    @rx.event
    def open_edit_dialog(self, profile_id: str) -> None:
        """Open the dialog on an existing profile's current configuration.

        The bindings are shown exactly as stored, including an id whose knowledge base has since been
        deleted: a configuration screen has to show what was configured. Such an id simply has no
        checkbox to appear in, and re-saving the form drops it.
        """
        profile = next((item for item in self._profiles if item.id == profile_id), None)
        if profile is None:
            raise ReflexAppException("This chat profile is no longer in the list. Refresh the page.")

        self._editing_profile_id = profile.id
        self.form_name = profile.name
        self.form_system_prompt = profile.system_prompt
        self.form_model = profile.model
        self.form_top_k = str(profile.top_k)
        self.form_score_threshold = (
            "" if profile.score_threshold is None else str(profile.score_threshold)
        )
        self.form_knowledge_base_ids = list(profile.knowledge_base_ids)
        self.dialog_open = True

    @rx.event
    def close_dialog(self) -> None:
        """Close the dialog, discarding whatever was typed."""
        self.dialog_open = False

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
                        service.update_profile(profile_id, save_dto)
                    else:
                        service.create_profile(save_dto)
                except PROFILE_SAVE_ERRORS as err:
                    # Both messages were written for a user; a toast is where they belong.
                    raise ReflexAppException(str(err)) from err
        finally:
            self.is_saving = False

        self.dialog_open = False
        await self._reload_profiles()
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
        chat_state.start_chat_with_profile(profile_id)
        return rx.redirect(KNOWLEDGE_BASE_CHAT_ROUTE)

    ############################################### PUBLISH ###############################################

    @rx.event
    async def publish_profile(self, profile_id: str) -> AsyncGenerator[rx.event.EventType, None]:
        """Publish (or re-publish, rotating the token) a chat profile.

        The service restricts this to lab admins and mints a fresh token every time, so calling this
        on an already-published profile revokes its previous token as a side effect. The minted
        token is shown exactly once, in the dialog this opens — confirmation of the consequences
        happens in the caller, before this event fires.
        """
        self.busy_profile_id = profile_id
        # Flushed before the publish runs, so the row's own spinner is seen — see ``load_page``.
        yield
        name = next((item.name for item in self._profiles if item.id == profile_id), "")
        try:
            main_state = await self.get_state(ReflexMainState)
            service = RagChatProfileService()
            with await main_state.authenticate_user():
                token = service.publish_profile(profile_id)
        finally:
            self.busy_profile_id = ""

        await self._reload_profiles()
        self.minted_token = token
        self.minted_token_profile_name = name
        self.token_dialog_open = True

    @rx.event
    async def unpublish_profile(self, profile_id: str) -> AsyncGenerator[rx.event.EventType, None]:
        """Un-publish a chat profile, revoking access for anyone holding its token immediately."""
        self.busy_profile_id = profile_id
        # Flushed before the un-publish runs, so the row's own spinner is seen — see ``load_page``.
        yield
        name = next((item.name for item in self._profiles if item.id == profile_id), "")
        try:
            main_state = await self.get_state(ReflexMainState)
            service = RagChatProfileService()
            with await main_state.authenticate_user():
                service.unpublish_profile(profile_id)
        finally:
            self.busy_profile_id = ""

        await self._reload_profiles()
        yield rx.toast.success(f"Chat profile '{name}' unpublished. Its previous token no longer works.")

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
        the restore path reports — so this deletes a configuration, not a history. Confirmation is the
        caller's: the button that reaches this sits behind an alert dialog.
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
        yield rx.toast.success(f"Chat profile '{name}' deleted.")

    ############################################### INTERNALS ###############################################

    @staticmethod
    def _published_label(profile: RagChatProfileDTO) -> str:
        """"Since when, by whom" for a published profile, or "" when it is not published."""
        if not profile.is_published or profile.published_at is None:
            return ""

        since = profile.published_at.strftime("%Y-%m-%d")
        if profile.published_by_email:
            return f"Since {since} by {profile.published_by_email}"
        return f"Since {since}"

    async def _reload_profiles(self) -> None:
        """Re-read the profile list. Callable from the backend, unlike the events above."""
        main_state = await self.get_state(ReflexMainState)
        with await main_state.authenticate_user():
            self._profiles = [
                profile.to_dto() for profile in RagChatProfileService().get_all_profiles()
            ]
