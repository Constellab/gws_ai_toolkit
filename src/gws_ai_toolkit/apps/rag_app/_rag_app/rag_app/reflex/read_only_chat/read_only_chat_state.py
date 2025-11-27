import json

import reflex as rx
from gws_ai_toolkit.models.chat.chat_conversation import ChatConversation
from gws_ai_toolkit.models.chat.chat_conversation_service import ChatConversationService

from ..chat_base.conversation_chat_state_base import ConversationChatStateBase


class ReadOnlyChatState(ConversationChatStateBase, rx.State):
    """State management for read-only conversation display.

    This state class extends ConversationChatStateBase to provide read-only viewing of
    historical conversations. It prevents user input while maintaining full
    message display functionality with proper styling and source citations.

    Key Features:
        - Read-only conversation display
        - Historical message rendering
        - Configuration dialog integration
        - Disabled user input handling
        - Source citation display

    The state is initialized with historical conversation data and provides
    viewing capabilities without allowing new messages or interactions.
    """

    # Override UI configuration for read-only mode
    title: str = "Conversation History"
    subtitle: str | None = None
    placeholder_text: str = "This is a read-only conversation"
    empty_state_message: str = "No messages in this conversation"
    clear_button_text: str = "Close"

    # Configuration dialog state
    show_config_dialog: bool = False
    current_configuration: dict = {}

    async def initialize_with_conversation_id(self, conversation_id: str) -> None:
        """Initialize the state by loading a conversation from the database.

        Args:
            conversation_id: The ID of the conversation to load
        """
        # Load the full conversation from database
        conversation_service = ChatConversationService()
        conversation = ChatConversation.get_by_id(conversation_id)

        if conversation:
            # Load messages for this conversation
            self._chat_messages = conversation_service.get_messages_of_conversation(conversation_id)

            # Update title with conversation info
            mode_display = conversation.mode.replace("_", " ").title()
            self.title = f"{mode_display} - {conversation.label[:50]}{'...' if len(conversation.label) > 50 else ''}"

            # Set subtitle with timestamp
            try:
                self.subtitle = f"Created on {conversation.last_modified_at.strftime('%B %d, %Y at %I:%M %p')}"
            except:
                self.subtitle = f"Last modified: {str(conversation.last_modified_at)}"

    async def create_conversation(self) -> None:
        """Override to prevent any AI calls in read-only mode."""
        # This should never be called in read-only mode
        pass

    @rx.event
    def open_config_dialog(self):
        """Open the configuration dialog."""
        self.show_config_dialog = True

    @rx.event
    def close_config_dialog(self):
        """Close the configuration dialog."""
        self.show_config_dialog = False

    @rx.var
    def config_json_string(self) -> str:
        """Get the current configuration as a formatted JSON string."""
        try:
            return json.dumps(self.current_configuration, indent=2, ensure_ascii=False)
        except Exception:
            return json.dumps({"error": "Failed to serialize configuration"}, indent=2)
