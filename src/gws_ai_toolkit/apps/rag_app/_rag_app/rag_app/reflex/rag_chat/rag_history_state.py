import reflex as rx
from gws_ai_toolkit.models.chat.conversation.base_chat_conversation import ChatConversationMode

from ..ai_expert.ai_expert_state import AiExpertState
from ..history.history_state import SidebarHistoryListState
from .rag_chat_state import RagChatState

# Maps conversation mode to the URL pattern for loading that conversation.
# The placeholder {id} is replaced with the actual conversation ID.
DEFAULT_MODE_ROUTE_MAP: dict[str, str] = {
    ChatConversationMode.RAG.value: "/chat/{id}",
    ChatConversationMode.AI_EXPERT.value: "/ai-expert/chat/{id}",
}

# Default route used when the conversation mode is not in the map
DEFAULT_CONVERSATION_ROUTE = "/chat/{id}"


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

        Looks for ``/chat/<id>`` in the URL path, which matches both
        ``/chat/[conversation_id]`` and ``/ai-expert/chat/[conversation_id]``.
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
        """Start a new chat based on the current page context.

        - On AI Expert pages with a document selected: creates a new AI Expert
          conversation for the same document.
        - On AI Expert pages without a document: does nothing.
        - On RAG chat pages: clears chat and navigates to /.
        """
        current_path = self.router.url.path

        if current_path.startswith("/ai-expert"):
            ai_expert_state: AiExpertState = await self.get_state(AiExpertState)
            resource = ai_expert_state._rag_resource
            if not resource:
                return

            ai_expert_state.clear_chat()
            resource_id = resource.get_id()
            return rx.redirect(f"/ai-expert/{resource_id}")

        rag_chat_state: RagChatState = await self.get_state(RagChatState)
        rag_chat_state.clear_chat()

        return rx.redirect("/")
