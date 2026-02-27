import reflex as rx
from gws_ai_toolkit.models.chat.chat_conversation_dto import ChatConversationDTO
from gws_ai_toolkit.models.chat.chat_conversation_service import ChatConversationService
from gws_reflex_main import ReflexMainState

from ..core.app_config_state import AppConfigState


class HistoryState(rx.State):
    """State management for conversation history browsing interface.

    This state class manages the history page functionality, handling conversation
    loading, selection, and display. It coordinates between the conversation list
    sidebar and the read-only conversation display panel.

    Key Features:
        - Conversation list loading and management
        - Conversation selection and highlighting
        - Integration with read-only chat display
        - Loading state management
        - Error handling for history operations

    State Attributes:
        conversations (List[ChatConversationDTO]): All available conversations
        selected_conversation_id (Optional[str]): Currently selected conversation
        is_loading (bool): Loading state for conversation fetching
    """

    # List of conversations to display in the left panel
    conversations: list[ChatConversationDTO] = []

    # Currently selected conversation
    selected_conversation_id: str | None = None

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
