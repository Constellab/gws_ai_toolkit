"""State of the knowledge-base chat window: ask a profile a question, get an attributed answer.

This mirrors the retired ``RagChatState`` — same base, same streaming, same history refresh — and
differs in the three places the embedded stack differs.

**The profile is the configuration.** A new conversation is built from the selected profile;
a restored one is built from the profile recorded in its own row, never from whatever the selector
happens to show. Both go through
:class:`~gws_ai_toolkit.models.knowledge_base.knowledge_base_chat_factory.KnowledgeBaseChatFactory`,
which is also what the future HTTP route uses, so there is one assembly rather than two.

**A conversation that cannot be continued is read, not restored.** A legacy ``rag`` row, a row of
another mode, a row whose profile was deleted: the messages still load and render, and
:attr:`read_only_notice` says why the input is gone. That is the difference between "this conversation
used a retired engine" and a stack trace.

**A source pill opens through its document's own provider.** A lab resource offers a share link, and
everything else falls back to the snapshot — the one copy guaranteed to exist. Which of the two, and
how it reaches the browser, is
:func:`~.core.document_open_action.build_open_document_event`'s decision, not this state's.

Nothing live is held on this state: no engine, no LanceDB connection, no API key. The conversation
object it carries is pickled between events, and the retriever inside it builds its engine per call.
"""

from dataclasses import dataclass

import reflex as rx
from gws_ai_toolkit.models.chat.conversation.base_chat_conversation import BaseChatConversation
from gws_ai_toolkit.models.chat.message.chat_user_message import (
    ChatUserMessageBase,
    ChatUserMessageText,
)
from gws_ai_toolkit.models.knowledge_base.knowledge_base_chat_factory import (
    KnowledgeBaseChatFactory,
    KnowledgeBaseChatUnavailableError,
)
from gws_ai_toolkit.models.knowledge_base.knowledge_base_dto import (
    DocumentIndexStatus,
    KnowledgeBaseDocumentDTO,
)
from gws_ai_toolkit.models.knowledge_base.knowledge_base_service import KnowledgeBaseService
from gws_ai_toolkit.models.knowledge_base.rag_chat_profile_dto import RagChatProfileDTO
from gws_ai_toolkit.models.knowledge_base.rag_chat_profile_service import RagChatProfileService
from gws_core import NotFoundException
from gws_reflex_main import ReflexAppException, ReflexMainState

from ...chat_base.conversation_chat_state_base import ConversationChatStateBase
from ...core.app_config_state import AppConfigState
from ...history.history_state import HistoryState
from ..core.document_open_action import build_open_document_event
from ..core.knowledge_base_app_state import KnowledgeBaseAppState

# New chat, and the page a restored conversation's URL is a child of.
KNOWLEDGE_BASE_CHAT_ROUTE = "/kb"
KNOWLEDGE_BASE_CONVERSATION_ROUTE = "/kb/chat/{id}"

PLACEHOLDER_TEXT = "Ask a question about your documents..."


@dataclass
class ChatProfileOption:
    """One entry of the header's profile selector.

    Attributes:
        id: The profile's id, which is what selecting it sets.
        name: What the selector shows.
    """

    id: str
    name: str


@dataclass
class DocumentFocusOption:
    """One document, as the focus picker's menu and chips show it.

    Attributes:
        id: The document's id, which is what a search is scoped to.
        filename: What the menu item and the chip show.
    """

    id: str
    filename: str


class KnowledgeBaseChatState(ConversationChatStateBase, rx.State):
    """A chat against a chat profile, streaming an answer with the sources it retrieved.

    Attributes:
        selected_profile_id: The profile a *new* conversation will run with.
        read_only_notice: Why the conversation on screen cannot be continued; empty when it can.
    """

    selected_profile_id: str = ""
    read_only_notice: str = ""

    placeholder_text: str = PLACEHOLDER_TEXT

    # The selectable profiles. A backend var: the selector needs an id and a name, while a profile
    # DTO carries a whole system prompt, and this list would otherwise be pushed to the browser once
    # per profile on every state sync. :attr:`profile_options` is what the UI reads.
    _profiles: list[RagChatProfileDTO] = []

    # Document Focus (issue #29). `_focused_document_ids` is what the next message carries;
    # `_focusable_documents` is what the "+" menu offers — the selected profile's bound knowledge
    # bases, refreshed whenever the profile changes (selecting one, restoring a conversation).
    _focused_document_ids: list[str] = []
    _focusable_documents: list[KnowledgeBaseDocumentDTO] = []

    ############################################### DERIVED ###############################################

    @rx.var
    def profile_options(self) -> list[ChatProfileOption]:
        """The profiles as the selector shows them."""
        return [ChatProfileOption(id=profile.id, name=profile.name) for profile in self._profiles]

    @rx.var
    def has_profiles(self) -> bool:
        """True when at least one profile exists to chat with."""
        return len(self._profiles) > 0

    @rx.var
    def selected_profile_name(self) -> str:
        """Name of the selected profile, for the header and the empty state."""
        for profile in self._profiles:
            if profile.id == self.selected_profile_id:
                return profile.name
        return ""

    @rx.var
    def is_read_only(self) -> bool:
        """True when the conversation on screen can be read but not continued."""
        return self.read_only_notice != ""

    @rx.var
    def focus_options(self) -> list[DocumentFocusOption]:
        """Documents the "+" menu offers: focusable, and not focused already."""
        return [
            DocumentFocusOption(id=document.id, filename=document.filename)
            for document in self._focusable_documents
            if document.id not in self._focused_document_ids
        ]

    @rx.var
    def focused_documents(self) -> list[DocumentFocusOption]:
        """The currently focused documents, rendered as removable chips."""
        filenames_by_id = self.document_filenames_by_id
        return [
            DocumentFocusOption(
                id=document_id, filename=filenames_by_id.get(document_id, document_id)
            )
            for document_id in self._focused_document_ids
        ]

    @rx.var
    def document_filenames_by_id(self) -> dict[str, str]:
        """Filename of every focusable document, by id.

        The lookup a historical message's read-only focus chips render against: a message only
        carries document ids (see :class:`ChatUserMessageText`), and this is the same set of
        documents that could have been focused on it, since focus never reaches outside the
        conversation's bound profile.
        """
        return {document.id: document.filename for document in self._focusable_documents}

    ############################################### CONVERSATION ###############################################

    async def _create_conversation(self) -> BaseChatConversation:
        """Build a new conversation against the selected profile.

        :raises ReflexAppException: if the conversation on screen is read-only, if no profile is
                selected, or if the selected profile has since been deleted
        """
        if self.read_only_notice:
            raise ReflexAppException(self.read_only_notice)

        factory = await self._build_factory()
        try:
            return factory.build_conversation(self.selected_profile_id)
        except KnowledgeBaseChatUnavailableError as err:
            raise ReflexAppException(str(err)) from err

    async def _restore_conversation(self, conversation_id: str) -> None:
        """Reopen a persisted conversation on the profile its own row records.

        Whether the conversation *can* be reopened is settled before the factory is built, and that
        order matters: building one resolves the chat credentials, so a lab whose credentials are
        misconfigured would answer a retired conversation with a credentials error instead of saying
        the engine is retired.

        :raises KnowledgeBaseChatUnavailableError: if it cannot be continued; the caller turns that
                into the read-only notice rather than an error, because the transcript is still worth
                reading
        """
        # The composer's default follows the conversation being opened, not whatever was picked on
        # the one being left. ``load_conversation`` has already refreshed ``_chat_messages`` for this
        # conversation by the time this runs, so its last user message is what to hydrate from.
        self._focused_document_ids = self._focus_of_last_user_message()

        main_state = await self.get_state(ReflexMainState)
        with await main_state.authenticate_user():
            KnowledgeBaseChatFactory.get_restorable_profile_id(conversation_id)

        factory = await self._build_factory()
        with await main_state.authenticate_user():
            conversation = factory.restore_conversation(conversation_id)

        self._conversation = conversation
        # The selector follows the conversation, so the header shows what is actually answering.
        self.selected_profile_id = conversation.knowledge_agent.get_chat_profile_id()
        await self._load_focusable_documents()

    async def build_user_message(self, user_query: str) -> ChatUserMessageBase:
        """Attach the current focus, if any, to the outgoing message.

        Document Focus (issue #29) rides the message itself rather than the conversation, so the
        scope that reaches ``KnowledgeBaseAgentAi`` is exactly what was focused when this message
        was sent — not whatever the picker shows by the time a later turn runs.
        """
        return ChatUserMessageText(
            content=user_query, focused_document_ids=list(self._focused_document_ids)
        )

    async def _after_conversation_updated(self) -> rx.event.EventSpec | None:
        """Refresh the sidebar and put the new conversation's id in the URL."""
        async with self:
            history_state = await self.get_state(HistoryState)
            await history_state.load_conversations()

        # Silently update the browser URL so a reload lands on this conversation
        # (replaceState, so no page reload and no extra history entry).
        if self._conversation and self._conversation._conversation_id:
            url = KNOWLEDGE_BASE_CONVERSATION_ROUTE.replace(
                "{id}", self._conversation._conversation_id
            )
            return rx.call_script(f'window.history.replaceState({{}}, "", "{url}")')
        return None

    ############################################### PAGE LOAD ###############################################

    @rx.event
    async def load_conversation_from_url(self) -> rx.event.EventType | None:
        """Handle page load for ``/kb/chat/[conversation_id]``.

        A conversation that cannot be continued is *shown* rather than refused: its messages are
        already loaded by the time the restore is attempted, so the page becomes a read-only
        transcript carrying the reason. An id that matches no conversation at all is different — there
        is no transcript to show — so that lands back on a blank chat.
        """
        conversation_id = getattr(self, "conversation_id", None)
        if not conversation_id:
            return None

        # Already viewing this conversation — a reload of the same page must not re-fetch it.
        if self._conversation and self._conversation._conversation_id == conversation_id:
            return None

        self.read_only_notice = ""
        await self._load_profiles()
        try:
            await self.load_conversation(conversation_id)
        except KnowledgeBaseChatUnavailableError as err:
            # ``load_conversation`` loaded the messages before restoring failed, so the transcript is
            # on screen; this is what replaces the input.
            self.read_only_notice = str(err)
        except NotFoundException:
            # A stale link or a deleted conversation. Nothing to read, so nothing to keep on screen.
            self.discard_conversation()
            return rx.redirect(KNOWLEDGE_BASE_CHAT_ROUTE)
        return None

    @rx.event
    async def load_new_chat_page(self) -> None:
        """Handle page load for ``/kb``, which always means a new chat.

        A conversation of its own has a URL of its own (``/kb/chat/<id>``), so arriving here means
        leaving whatever was on screen — the conversation object included, not just the read-only
        notice. Dropping only the notice would leave the previous transcript rendered and, worse, let
        the next question be appended to the conversation the user had just navigated away from.
        """
        self.discard_conversation()
        await self._load_profiles()

    @rx.event
    async def on_mount(self) -> None:
        """Load the profiles, the sidebar history, and pick a profile if none is selected."""
        await self._load_profiles()

        history_state = await self.get_state(HistoryState)
        await history_state.load_conversations()

    @rx.event
    async def start_new_chat(self) -> rx.event.EventType:
        """Drop the conversation on screen and go back to a blank chat on the same profile."""
        self.discard_conversation()
        return rx.redirect(KNOWLEDGE_BASE_CHAT_ROUTE)

    @rx.event
    async def select_profile(self, profile_id: str) -> rx.event.EventType | None:
        """Switch profile, which starts a new conversation.

        A conversation's profile is recorded on its row and its answers were produced by that
        profile; continuing it under another one would change the answers halfway through. So
        choosing a profile while a conversation is open starts a fresh one instead.
        """
        if profile_id == self.selected_profile_id and not self.read_only_notice:
            return None

        had_conversation = bool(self._conversation or self._chat_messages or self.read_only_notice)
        await self.start_chat_with_profile(profile_id)
        return rx.redirect(KNOWLEDGE_BASE_CHAT_ROUTE) if had_conversation else None

    @rx.event
    def clear_chat(self) -> None:
        """Clear the chat and reset the conversation, dropping any focus set on it."""
        super().clear_chat()
        self._focused_document_ids = []

    def discard_conversation(self) -> None:
        """Leave the conversation on screen, keeping the selected profile.

        The one place the two halves of "nothing is open" are cleared together — the conversation
        object *and* the read-only notice. Clearing one without the other is what makes a stale
        transcript answer a new question, or a retired-engine notice hang over a blank chat.

        Not an event: ``RagHistoryState`` reaches it through ``get_state``, and the ``/kb`` page load
        calls it directly.
        """
        self.clear_chat()
        self.read_only_notice = ""

    async def start_chat_with_profile(self, profile_id: str) -> None:
        """Select a profile and leave whatever was on screen.

        Not an event, for the same reason as :meth:`discard_conversation`: the chat-profile page
        reaches this through ``get_state`` and then redirects itself, which is how the *Chat* button on
        a profile row lands on a blank chat with that profile already selected.
        """
        self.selected_profile_id = profile_id
        self.discard_conversation()
        await self._load_focusable_documents()

    ############################################### DOCUMENT FOCUS ###############################################

    def _focus_of_last_user_message(self) -> list[str]:
        """The focus the composer should default to: whatever the conversation's own last message
        carried, so restoring a conversation re-hydrates the sticky default rather than resetting it.
        """
        for message in reversed(self._chat_messages):
            if isinstance(message, ChatUserMessageText):
                return list(message.focused_document_ids)
        return []

    @rx.event
    def add_document_focus(self, document_id: str) -> None:
        """Add a document to the focus of the current (or next) message."""
        if document_id not in self._focused_document_ids:
            self._focused_document_ids = [*self._focused_document_ids, document_id]

    @rx.event
    def remove_document_focus(self, document: DocumentFocusOption) -> None:
        """Remove a document from the current focus."""
        self._focused_document_ids = [
            document_id for document_id in self._focused_document_ids if document_id != document.id
        ]

    ############################################### SOURCES ###############################################

    @rx.event
    async def open_document(self, document_id: str) -> rx.event.EventType | None:
        """Open a source document the way its own provider says to.

        ``document_id`` is a :class:`KnowledgeBaseDocument` id here, not a RAGFlow document id: the
        chunk that produced the pill carries the row it was indexed from. What "open" means is the
        provider's decision — a share link for a lab resource, the stored snapshot otherwise — and
        :func:`build_open_document_event` is the one place that turns it into an event.

        :param document_id: the knowledge-base document behind the clicked source pill
        :raises ReflexAppException: if the document is no longer in the knowledge base
        """
        main_state = await self.get_state(ReflexMainState)

        with await main_state.authenticate_user():
            document = KnowledgeBaseService().get_document(document_id)
            if document is None:
                raise ReflexAppException(
                    "This document is no longer in the knowledge base, so it cannot be opened."
                )
            return build_open_document_event(document)

    ############################################### INTERNALS ###############################################

    async def _build_factory(self) -> KnowledgeBaseChatFactory:
        """The factory that assembles this chat, with everything resolved per call.

        The retriever, the API key and the chat app name are read here rather than cached: a key is a
        secret that has no business on a serialised state, and resolving them is a couple of indexed
        queries.
        """
        main_state = await self.get_state(ReflexMainState)
        app_state = await self.get_state(KnowledgeBaseAppState)
        app_config_state = await AppConfigState.get_instance(self)

        user = await main_state.get_current_user()

        return KnowledgeBaseChatFactory(
            chat_app_name=await app_config_state.get_chat_app_name(),
            retriever=await app_state.build_retriever(main_state),
            api_key=await app_state.get_chat_api_key(main_state),
            user=user.to_dto() if user else None,
        )

    async def _load_profiles(self) -> None:
        """Re-read the selectable profiles, selecting the first one if nothing is selected yet.

        Selecting a default matters: without one, the first question of a fresh app would be refused
        for a reason the user did nothing to cause.
        """
        main_state = await self.get_state(ReflexMainState)
        with await main_state.authenticate_user():
            self._profiles = [
                profile.to_dto() for profile in RagChatProfileService().get_all_profiles()
            ]

        selectable_ids = [profile.id for profile in self._profiles]
        if self.selected_profile_id not in selectable_ids:
            self.selected_profile_id = selectable_ids[0] if selectable_ids else ""

        await self._load_focusable_documents()

    async def _load_focusable_documents(self) -> None:
        """Re-read the documents the focus picker offers: the selected profile's bound, indexed
        knowledge bases.

        Focus only narrows the profile's own scope, never widens it (see ADR-0002), so a document of
        a knowledge base the profile does not bind must never appear here. Only ``done`` documents
        are offered — a document still indexing, or one whose indexing failed, has nothing to
        retrieve from yet.
        """
        if not self.selected_profile_id:
            self._focusable_documents = []
            return

        main_state = await self.get_state(ReflexMainState)
        with await main_state.authenticate_user():
            profile_service = RagChatProfileService()
            profile = profile_service.get_profile(self.selected_profile_id)
            if profile is None:
                self._focusable_documents = []
                return

            knowledge_base_ids = profile_service.get_valid_knowledge_base_ids(profile)
            service = KnowledgeBaseService()
            self._focusable_documents = [
                document.to_dto()
                for knowledge_base_id in knowledge_base_ids
                for document in service.get_documents(knowledge_base_id)
                if document.index_status == DocumentIndexStatus.DONE.value
            ]
