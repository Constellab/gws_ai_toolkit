from datetime import datetime
from typing import Optional

from gws_ai_toolkit.rag.rag_app._rag_app.rag_app.components.conversation_history.conversation_history_class import \
    ConversationHistory
from gws_ai_toolkit.rag.rag_app._rag_app.rag_app.components.generic_chat.chat_state_base import \
    ChatStateBase
from gws_ai_toolkit.rag.rag_app._rag_app.rag_app.states.rag_main_state import \
    RagAppState


class ReadOnlyChatState(RagAppState, ChatStateBase):
    """Read-only chat state for displaying historical conversations."""

    # Override UI configuration for read-only mode
    title: str = "Conversation History"
    subtitle: Optional[str] = None
    placeholder_text: str = "This is a read-only conversation"
    empty_state_message: str = "No messages in this conversation"
    clear_button_text: str = "Close"

    def initialize_with_conversation(self, conversation: ConversationHistory) -> None:
        """Initialize the state with a historical conversation.

        Args:
            conversation: The conversation history to display
        """
        self.conversation_id = conversation.conversation_id
        self._chat_messages = conversation.messages.copy()
        self._current_response_message = None
        self.is_streaming = False

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
