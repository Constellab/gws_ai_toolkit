import reflex as rx
from gws_ai_toolkit.models.chat.chat_conversation import ChatConversation
from gws_ai_toolkit.models.chat.chat_conversation_service import ChatConversationService
from gws_ai_toolkit.models.chat.conversation.base_chat_conversation import (
    BaseChatConversation,
    BaseChatConversationConfig,
)
from gws_ai_toolkit.models.chat.conversation.rag_chat_config import RagChatConfig
from gws_ai_toolkit.models.chat.conversation.rag_chat_conversation import RagChatConversation
from gws_ai_toolkit.rag.common.base_rag_app_service import BaseRagAppService
from gws_ai_toolkit.rag.common.tag_rag_app_service import TagRagAppService
from gws_reflex_main import ReflexMainState

from ..chat_base.conversation_chat_state_base import ConversationChatStateBase
from ..history.history_state import HistoryState
from .config.rag_config_state import RagConfigState
from .rag_chat_config_state import RagChatConfigState


class RagChatState(ConversationChatStateBase, rx.State):
    """State management for RAG (Retrieval Augmented Generation) chat functionality.

    This state class implements the main RAG chat system using the new
    ConversationChatStateBase and RagChatConversation architecture.
    It provides intelligent conversations enhanced with document knowledge
    from indexed sources.

    Key Features:
        - RAG-enhanced conversation with document knowledge
        - Streaming AI responses with real-time updates
        - Source citation and document references
        - Integration with multiple RAG providers
        - Automatic conversation persistence
        - Error handling and fallback mechanisms

    The state connects to configured RAG services and processes user queries
    by retrieving relevant document chunks and generating contextual responses
    with proper source attribution.
    """

    async def _create_conversation(self) -> BaseChatConversation:
        """Create a new RagChatConversation instance.

        Gets the RAG app service from RagConfigState and creates a
        RagChatConversation configured with it.

        Returns:
            BaseChatConversation: A new RagChatConversation configured with
                the RAG app service from RagConfigState.
        """
        rag_config_state = await RagConfigState.get_instance(self)

        rag_service = await rag_config_state.get_chat_rag_service()
        if not rag_service:
            raise ValueError("RAG chat service not available")

        chat_app_name = await rag_config_state.get_chat_app_name()

        main_state = await self.get_state(ReflexMainState)
        user = await main_state.get_current_user()

        conv_config = BaseChatConversationConfig(
            chat_app_name, store_conversation_in_db=True, user=user.to_dto() if user else None
        )

        return RagChatConversation(
            config=conv_config,
            rag_service=rag_service,
            rag_chat_id=await rag_config_state.get_chat_id_and_check(),
        )

    async def _restore_conversation(self, conversation_id: str) -> None:
        """Restore a RagChatConversation for an existing conversation.

        Creates the RagChatConversation, sets its internal IDs, and loads
        the existing messages so it can continue the conversation.
        """
        conversation = await self._create_conversation()

        # Restore the conversation's internal state from the database
        main_state = await self.get_state(ReflexMainState)
        with await main_state.authenticate_user():
            db_conversation: ChatConversation = ChatConversation.get_by_id_and_check(conversation_id)
            conversation._conversation_id = conversation_id
            conversation._external_conversation_id = db_conversation.external_conversation_id

            # Load existing messages into the conversation object
            conversation_service = ChatConversationService()
            conversation.chat_messages = conversation_service.get_messages_of_conversation(conversation_id)

        self._conversation = conversation

    async def _after_conversation_updated(self) -> rx.event.EventSpec | None:
        """Refresh the sidebar conversation list and update URL after a message is sent."""
        async with self:
            history_state = await self.get_state(HistoryState)
            await history_state.load_conversations()

            # Update the active conversation ID in the sidebar
            if self._conversation and self._conversation._conversation_id:
                from .chat_history_sidebar_state import ChatHistorySidebarState

                sidebar_state = await self.get_state(ChatHistorySidebarState)
                sidebar_state.active_conversation_id = self._conversation._conversation_id

        # Silently update the browser URL to include the conversation ID
        # (uses replaceState to avoid a full page reload)
        if self._conversation and self._conversation._conversation_id:
            conversation_id = self._conversation._conversation_id
            return rx.call_script(
                f'window.history.replaceState({{}}, "", "/chat/{conversation_id}")'
            )
        return None

    @rx.event
    async def load_conversation_from_url(self) -> None:
        """Handle page load for /chat/[conversation_id] route.

        Reads conversation_id from the URL parameter and loads the
        conversation into the chat state. Follows the same pattern as
        AiExpertState.load_resource_from_url.
        """
        conversation_id = self.conversation_id if hasattr(self, "conversation_id") else None

        if not conversation_id:
            return

        # Avoid reloading if already viewing this conversation
        if self._conversation and self._conversation._conversation_id == conversation_id:
            return

        try:
            await self.load_conversation(conversation_id)
        except Exception:
            # Conversation not found or access denied — redirect to new chat
            self.clear_chat()
            return rx.redirect("/")

        # Sync the sidebar's active conversation ID
        from .chat_history_sidebar_state import ChatHistorySidebarState

        sidebar_state = await self.get_state(ChatHistorySidebarState)
        sidebar_state.active_conversation_id = conversation_id

    @rx.event(background=True)
    async def on_mount(self) -> None:
        """Load configuration and update UI properties."""

        rag_app_service: BaseRagAppService | None
        async with self:
            # Load placeholder text from config
            rag_chat_config_state = await self.get_state(RagChatConfigState)
            config: RagChatConfig = await rag_chat_config_state.get_config()
            self.placeholder_text = config.placeholder_text
            rag_config_state = await RagConfigState.get_instance(self)
            rag_app_service = await rag_config_state.get_chat_rag_app_service()

        if rag_app_service and isinstance(rag_app_service, TagRagAppService):
            count_resources = rag_app_service.count_synced_resources()
            async with self:
                self.subtitle = f"{count_resources} files in the database"

        # Load sidebar conversations
        async with self:
            history_state = await self.get_state(HistoryState)
            await history_state.load_conversations()
