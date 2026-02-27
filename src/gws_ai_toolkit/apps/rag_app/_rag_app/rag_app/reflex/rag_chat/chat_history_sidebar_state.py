import reflex as rx
from gws_ai_toolkit.models.chat.conversation.base_chat_conversation import ChatConversationMode

from .rag_chat_state import RagChatState

# Maps conversation mode to the URL pattern for loading that conversation.
# The placeholder {id} is replaced with the actual conversation ID.
DEFAULT_MODE_ROUTE_MAP: dict[str, str] = {
    ChatConversationMode.RAG.value: "/chat/{id}",
    ChatConversationMode.AI_EXPERT.value: "/ai-expert/chat/{id}",
}

# Default route used when the conversation mode is not in the map
DEFAULT_CONVERSATION_ROUTE = "/chat/{id}"

# Route prefix for AI Expert pages
AI_EXPERT_ROUTE_PREFIX = "/ai-expert"


class ChatHistorySidebarState(rx.State):
    """State for the chat history sidebar on the main chat page.

    Coordinates between HistoryState (conversation list) and
    the active chat state when the user selects a conversation
    or starts a new chat.

    Routes conversations to the correct page based on their mode
    using a configurable mode-to-URL mapping.
    """

    # Track which conversation is active in the chat
    active_conversation_id: str | None = None

    # Mode-to-URL route mapping (can be overridden by the app)
    _mode_route_map: dict[str, str] = DEFAULT_MODE_ROUTE_MAP

    @classmethod
    def set_mode_route_map(cls, mode_route_map: dict[str, str]) -> None:
        """Set the mode-to-URL route mapping.

        :param mode_route_map: Dict mapping conversation mode strings to URL patterns.
            Use {id} as a placeholder for the conversation ID.
        """
        cls._mode_route_map = mode_route_map

    def _get_conversation_url(self, conversation_id: str, mode: str) -> str:
        """Get the URL for a conversation based on its mode."""
        route_pattern = self._mode_route_map.get(mode, DEFAULT_CONVERSATION_ROUTE)
        return route_pattern.replace("{id}", conversation_id)

    @rx.event
    async def select_conversation(self, conversation_id: str, mode: str):
        """Navigate to the conversation URL based on its mode.

        The on_load handler of the target page will load the conversation.
        """
        self.active_conversation_id = conversation_id
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
        self.active_conversation_id = None

        if current_path.startswith(AI_EXPERT_ROUTE_PREFIX):
            from ..ai_expert.ai_expert_state import AiExpertState

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
