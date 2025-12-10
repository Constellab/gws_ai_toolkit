import reflex as rx
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
