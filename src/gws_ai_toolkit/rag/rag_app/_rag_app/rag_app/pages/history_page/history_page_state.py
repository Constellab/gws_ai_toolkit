from typing import List, Optional

import reflex as rx

from gws_ai_toolkit.rag.rag_app._rag_app.rag_app.components.conversation_history.conversation_history_class import \
    ConversationHistory
from gws_ai_toolkit.rag.rag_app._rag_app.rag_app.components.conversation_history.conversation_history_state import \
    ConversationHistoryState
from gws_ai_toolkit.rag.rag_app._rag_app.rag_app.components.generic_chat.read_only_chat_state import \
    ReadOnlyChatState


class HistoryPageState(rx.State):
    """State management for the history page."""

    # List of conversations to display in the left panel
    conversations: List[ConversationHistory] = []

    # Currently selected conversation
    selected_conversation_id: Optional[str] = None

    # Loading state
    is_loading: bool = False

    @rx.event
    async def load_conversations(self):
        """Load all conversations from the history."""
        self.is_loading = True

        try:
            history_state: ConversationHistoryState = await self.get_state(ConversationHistoryState)

            full_history = await history_state.get_conversation_history()
            conversations = full_history.get_all_conversations()

            # Sort conversations by timestamp (newest first)
            conversations.sort(key=lambda x: x.timestamp, reverse=True)

            self.conversations = conversations
        finally:
            self.is_loading = False

    @rx.event
    async def select_conversation(self, conversation_id: str):
        """Select a conversation to display."""
        self.selected_conversation_id = conversation_id

        # Initialize the read-only chat state with the selected conversation
        selected_conv = next((c for c in self.conversations if c.conversation_id == conversation_id), None)
        if selected_conv:
            read_only_state: ReadOnlyChatState = await self.get_state(ReadOnlyChatState)
            read_only_state.initialize_with_conversation(selected_conv)

    @rx.var
    def selected_conversation(self) -> Optional[ConversationHistory]:
        """Get the currently selected conversation."""
        if not self.selected_conversation_id:
            return None
        return next((c for c in self.conversations if c.conversation_id == self.selected_conversation_id), None)

    @rx.var
    def has_conversations(self) -> bool:
        """Check if there are any conversations."""
        return len(self.conversations) > 0
