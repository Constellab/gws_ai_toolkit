import reflex as rx
from gws_ai_toolkit.models.chat.conversation.base_chat_conversation import ChatConversationMode

from ..history.history_state import SidebarHistoryListState
from ..knowledge_base.chat.knowledge_base_chat_state import (
    KNOWLEDGE_BASE_CHAT_ROUTE,
    KNOWLEDGE_BASE_CONVERSATION_ROUTE,
    KnowledgeBaseChatState,
)

# Maps conversation mode to the URL pattern for loading that conversation.
# The placeholder {id} is replaced with the actual conversation ID.
#
# A legacy ``rag`` or ``ai_expert`` conversation is routed to the knowledge-base chat page like any
# other: those rows were run against retired engines, so that page reports why they cannot be
# continued and shows their transcript read-only, rather than reopening a chat nothing can answer for.
DEFAULT_MODE_ROUTE_MAP: dict[str, str] = {
    ChatConversationMode.RAG.value: KNOWLEDGE_BASE_CONVERSATION_ROUTE,
    ChatConversationMode.KNOWLEDGE_BASE.value: KNOWLEDGE_BASE_CONVERSATION_ROUTE,
}

# Default route used when the conversation mode is not in the map. The knowledge-base chat is the
# honest destination for a mode this app has no page for: it reports what the conversation is and
# leaves its transcript readable, where a chat page would fail on restore.
DEFAULT_CONVERSATION_ROUTE = KNOWLEDGE_BASE_CONVERSATION_ROUTE


class RagHistoryState(SidebarHistoryListState, rx.State):
    """SidebarHistoryListState subclass for RAG-based apps with mode-based URL routing.

    Provides a configurable mode-to-URL mapping so that conversations of
    different modes (RAG, AI Expert, etc.) are routed to the correct page.

    Apps that extend this mixin only need to implement ``start_new_chat``.
    ``select_conversation`` is provided with a default implementation that
    navigates based on the mode route map.
    """

    # Mode-to-URL route mapping (can be overridden by the app)
    _mode_route_map: dict[str, str] = DEFAULT_MODE_ROUTE_MAP

    def get_active_conversation_id(self) -> str | None:
        """Extract the active conversation ID from the current URL.

        Looks for ``/chat/<id>`` in the URL path, which matches ``/chat/[conversation_id]``.
        """
        return self.conversation_id

    def _get_conversation_url(self, conversation_id: str, mode: str) -> str:
        """Get the URL for a conversation based on its mode."""
        route_pattern = self._mode_route_map.get(mode, DEFAULT_CONVERSATION_ROUTE)
        return route_pattern.replace("{id}", conversation_id)

    @rx.event
    async def select_conversation(self, conversation_id: str, mode: str):
        """Navigate to the conversation URL based on its mode."""
        url = self._get_conversation_url(conversation_id, mode)
        return rx.redirect(url)

    @rx.event
    async def start_new_chat(self):
        """Start a new chat: clear the knowledge-base chat and navigate to it.

        Every page wrapped by ``rag_page_layout_component`` is a knowledge-base page, so "New Chat"
        always means the same thing regardless of which one it was clicked from.
        """
        knowledge_base_chat_state: KnowledgeBaseChatState = await self.get_state(
            KnowledgeBaseChatState
        )
        knowledge_base_chat_state.discard_conversation()
        return rx.redirect(KNOWLEDGE_BASE_CHAT_ROUTE)
