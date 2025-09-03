import json
from typing import Optional

import reflex as rx

from ..chat_base.chat_state_base import ChatStateBase
from ..history.conversation_history_class import ConversationHistory


class ReadOnlyChatState(ChatStateBase, rx.State):
    """Read-only chat state for displaying historical conversations."""

    # Override UI configuration for read-only mode
    title: str = "Conversation History"
    subtitle: Optional[str] = None
    placeholder_text: str = "This is a read-only conversation"
    empty_state_message: str = "No messages in this conversation"
    clear_button_text: str = "Close"

    # Configuration dialog state
    show_config_dialog: bool = False
    current_configuration: dict = {}

    def initialize_with_conversation(self, conversation: ConversationHistory) -> None:
        """Initialize the state with a historical conversation.

        Args:
            conversation: The conversation history to display
        """
        self.conversation_id = conversation.conversation_id
        self._chat_messages = conversation.messages.copy()
        self._current_response_message = None
        self.is_streaming = False
        self.current_configuration = conversation.configuration

        # Update title with conversation info
        mode_display = conversation.mode.replace('_', ' ').title()
        self.title = f"{mode_display} - {conversation.label[:50]}{'...' if len(conversation.label) > 50 else ''}"

        # Set subtitle with timestamp
        try:
            self.subtitle = f"Created on {conversation.timestamp.strftime('%B %d, %Y at %I:%M %p')}"
        except:
            self.subtitle = f"Created on {str(conversation.timestamp)}"

    async def call_ai_chat(self, user_message: str) -> None:
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
