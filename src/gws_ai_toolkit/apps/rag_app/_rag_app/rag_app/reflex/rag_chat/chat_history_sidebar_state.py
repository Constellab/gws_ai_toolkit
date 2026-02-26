import reflex as rx

from .rag_chat_state import RagChatState


class ChatHistorySidebarState(rx.State):
    """State for the chat history sidebar on the main chat page.

    Coordinates between HistoryState (conversation list) and
    RagChatState (active chat) when the user selects a conversation
    or starts a new chat.
    """

    # Track which conversation is active in the chat
    active_conversation_id: str | None = None

    @rx.event
    async def select_conversation(self, conversation_id: str):
        """Navigate to the conversation URL. The on_load handler will load it."""
        self.active_conversation_id = conversation_id
        return rx.redirect(f"/chat/{conversation_id}")

    @rx.event
    async def start_new_chat(self):
        """Clear the chat and navigate to the base chat URL."""
        self.active_conversation_id = None

        rag_chat_state: RagChatState = await self.get_state(RagChatState)
        rag_chat_state.clear_chat()

        return rx.redirect("/")
