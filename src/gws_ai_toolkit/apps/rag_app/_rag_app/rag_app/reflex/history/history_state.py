import reflex as rx
from gws_ai_toolkit.models.chat.chat_conversation_dto import ChatConversationDTO
from gws_ai_toolkit.models.chat.chat_conversation_service import ChatConversationService
from gws_reflex_main import ReflexMainState

from ..core.app_config_state import AppConfigState
from ..read_only_chat.read_only_chat_state import ReadOnlyChatState


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
        finally:
            self.is_loading = False

    @rx.event
    async def select_conversation(self, conversation_id: str):
        """Select a conversation to display."""
        self.selected_conversation_id = conversation_id

        # Initialize read-only chat state
        read_only_state: ReadOnlyChatState = await self.get_state(ReadOnlyChatState)
        await read_only_state.initialize_with_conversation_id(conversation_id)

    @rx.var
    def selected_conversation(self) -> ChatConversationDTO | None:
        """Get the currently selected conversation."""
        if not self.selected_conversation_id:
            return None
        return next((c for c in self.conversations if c.id == self.selected_conversation_id), None)

    @rx.var
    def has_conversations(self) -> bool:
        """Check if there are any conversations."""
        return len(self.conversations) > 0
