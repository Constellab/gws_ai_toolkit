from abc import abstractmethod

import reflex as rx
from gws_ai_toolkit.models.chat.chat_conversation_dto import ChatConversationDTO
from gws_ai_toolkit.models.chat.chat_conversation_service import ChatConversationService
from gws_reflex_main import ReflexMainState

from ..core.app_config_state import AppConfigState


class HistoryState(rx.State):
    """Concrete state for conversation history data.

    Manages the conversation list and loading state.
    This is a normal rx.State (not a mixin) so it can be accessed directly
    via ``self.get_state(HistoryState)`` from any state.

    State Attributes:
        conversations: All available conversations.
        is_loading: Loading state for conversation fetching.
    """

    # List of conversations to display in the left panel
    conversations: list[ChatConversationDTO] = []

    # Loading state
    is_loading: bool = False

    # Whether conversations have been loaded at least once
    _conversations_loaded: bool = False

    @rx.event
    async def load_conversations_if_needed(self):
        """Load conversations only if they haven't been loaded yet."""
        if self._conversations_loaded:
            return
        await self.load_conversations()

    @rx.event
    async def load_conversations(self):
        """Load all conversations from the database."""
        self.is_loading = True

        try:
            # Get chat app name
            app_config_state = await AppConfigState.get_instance(self)
            main_state = await self.get_state(ReflexMainState)
            chat_app_name = await app_config_state.get_chat_app_name()

            # Get conversations using the service
            conversation_service = ChatConversationService()

            with await main_state.authenticate_user():
                conversations = conversation_service.get_my_conversations_by_chat_app(
                    chat_app_name=chat_app_name
                )

                # Convert ChatConversation models to ChatConversationDTOs
                self.conversations = [conv.to_dto() for conv in conversations]
                self._conversations_loaded = True
        finally:
            self.is_loading = False

    @rx.var
    def has_conversations(self) -> bool:
        """Check if there are any conversations."""
        return len(self.conversations) > 0


class SidebarHistoryListState(rx.State, mixin=True):
    """Abstract mixin state for sidebar navigation behavior.

    Provides abstract methods for ``select_conversation``, ``start_new_chat``,
    and ``get_active_conversation_id`` that concrete subclasses must implement.
    Each app defines its own subclass with the appropriate navigation logic.
    """

    @rx.var
    def active_conversation_id(self) -> str | None:
        """Reactive variable to track the active conversation ID."""
        return self.get_active_conversation_id()

    @abstractmethod
    def get_active_conversation_id(self) -> str | None:
        """Return the active conversation ID derived from the current URL.

        Concrete subclasses must implement this to extract the conversation ID
        from the URL based on the app's routing conventions.
        """

    @abstractmethod
    async def select_conversation(self, conversation_id: str, mode: str):
        """Handle selecting a conversation from the sidebar.

        Concrete subclasses must implement this to navigate to the
        appropriate page for the given conversation.

        :param conversation_id: The ID of the conversation to select.
        :param mode: The conversation mode string.
        """
