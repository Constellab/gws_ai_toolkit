import reflex as rx
from gws_ai_toolkit.models.chat.conversation.ai_expert_chat_conversation import (
    AiExpertChatConversation,
    AiExpertConfig,
)
from gws_ai_toolkit.models.chat.conversation.base_chat_conversation import (
    BaseChatConversation,
    BaseChatConversationConfig,
)
from gws_ai_toolkit.rag.common.rag_resource import RagResource
from gws_reflex_main import ReflexMainState

from ..chat_base.conversation_chat_state_base import ConversationChatStateBase
from ..rag_chat.config.rag_config_state import RagConfigState
from .ai_expert_config_state import AiExpertConfigState


class AiExpertState(ConversationChatStateBase, rx.State):
    """State management for AI Expert - specialized document-focused chat functionality.

    This state class manages the AI Expert workflow using the new
    ConversationChatStateBase and AiExpertChatConversation architecture.
    It provides intelligent conversation capabilities focused on a specific document
    using multiple processing modes.

    Key Features:
        - Document-specific chat with full context awareness
        - Multiple processing modes (full_file, relevant_chunks, full_text_chunk)
        - OpenAI integration with streaming responses
        - File upload to OpenAI for advanced analysis
        - Document chunk retrieval and processing
        - Automatic conversation persistence

    Processing Modes:
        - full_file: Uploads entire document to OpenAI with code interpreter access
        - relevant_chunks: Retrieves only most relevant document chunks for the query
        - full_text_chunk: Includes all document chunks as text in the AI prompt

    The state connects to configured RAG services and processes user queries
    about a specific document with proper context awareness.
    """

    # UI configuration
    title: str = "AI Expert"
    placeholder_text: str = "Ask about this document..."
    empty_state_message: str = "Start asking questions about this document"

    _rag_resource: RagResource | None = None

    async def _create_conversation(self) -> BaseChatConversation:
        """Create a new AiExpertChatConversation instance.

        Gets the RAG app service, configuration, and document resource
        to create a properly configured conversation.

        Returns:
            BaseChatConversation: A new AiExpertChatConversation configured with
                the RAG service and document.
        """
        # Get RAG app service
        if not self._rag_resource:
            raise ValueError("RAG resource not set for AI Expert conversation")

        rag_config_state = await RagConfigState.get_instance(self)
        rag_app_service = await rag_config_state.get_dataset_rag_app_service()
        if not rag_app_service:
            raise ValueError("RAG service not available")

        chat_app_name = await rag_config_state.get_chat_app_name()

        # Get config
        app_config_state = await self.get_state(AiExpertConfigState)
        config: AiExpertConfig = await app_config_state.get_config()

        main_state = await self.get_state(ReflexMainState)
        user = await main_state.get_current_user()

        conv_config = BaseChatConversationConfig(
            chat_app_name, store_conversation_in_db=True, user=user.to_dto() if user else None
        )

        return AiExpertChatConversation(
            config=conv_config,
            chat_config=config,
            rag_app_service=rag_app_service,
            rag_resource=self._rag_resource,
        )

    async def load_resource_from_url(self) -> None:
        """Handle page load - get resource ID from router state"""

        document_id = self.document_id if hasattr(self, "document_id") else None

        if not document_id:
            return None

        rag_resource = RagResource.from_document_or_resource_id_and_check(document_id)

        if not rag_resource:
            self.clear_chat()
            return None

        if self._rag_resource and self._rag_resource.get_id() != rag_resource.get_id():
            # Reset chat if loading a different file
            self.clear_chat()

        self.subtitle = rag_resource.resource_model.name
        self._rag_resource = rag_resource

    @rx.event
    async def open_current_resource_file(self):
        """Open the current resource file."""
        if self._rag_resource:
            return await self.open_document_from_resource(self._rag_resource.get_id())
        return None
