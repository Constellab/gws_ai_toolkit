import reflex as rx
from gws_ai_toolkit.models.chat.conversation.base_chat_conversation import BaseChatConversation
from gws_ai_toolkit.models.chat.conversation.rag_chat_conversation import RagChatConversation

from ..chat_base.conversation_chat_state_base import ConversationChatStateBase
from .config.rag_config_state import RagConfigState


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

    async def create_conversation(self) -> BaseChatConversation:
        """Create a new RagChatConversation instance.

        Gets the RAG app service from RagConfigState and creates a
        RagChatConversation configured with it.

        Returns:
            BaseChatConversation: A new RagChatConversation configured with
                the RAG app service from RagConfigState.
        """
        rag_app_state = await RagConfigState.get_instance(self)

        rag_app_service = await rag_app_state.get_chat_rag_app_service()
        if not rag_app_service:
            raise ValueError("RAG chat service not available")

        chat_app_name = await rag_app_state.get_chat_app_name()

        return RagChatConversation(
            chat_app_name=chat_app_name,
            # TODO check what to do with configuration
            configuration={},
            rag_app_service=rag_app_service,
            rag_chat_id=await rag_app_state.get_chat_id_and_check(),
        )

    def _after_chat_cleared(self):
        """Reset any RAG-specific state after chat is cleared."""
        pass
