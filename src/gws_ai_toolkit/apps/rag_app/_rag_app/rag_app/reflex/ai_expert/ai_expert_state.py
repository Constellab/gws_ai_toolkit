import reflex as rx
from gws_ai_toolkit.models.chat.chat_conversation import ChatConversation
from gws_ai_toolkit.models.chat.chat_conversation_service import ChatConversationService
from gws_ai_toolkit.models.chat.conversation.ai_expert_chat_config import AiExpertChatConfig
from gws_ai_toolkit.models.chat.conversation.ai_expert_chat_conversation import (
    AiExpertChatConversation,
)
from gws_ai_toolkit.models.chat.conversation.base_chat_conversation import (
    BaseChatConversation,
    BaseChatConversationConfig,
)
from gws_ai_toolkit.rag.common.rag_resource import RagResource
from gws_core import ResourceModel
from gws_reflex_main import ReflexMainState

from ..chat_base.conversation_chat_state_base import ConversationChatStateBase
from ..history.history_state import HistoryState
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
        config: AiExpertChatConfig = await app_config_state.get_config()

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

    async def _restore_conversation(self, conversation_id: str) -> None:
        """Restore an AiExpertChatConversation for an existing conversation.

        Loads the resource from the conversation's stored configuration,
        then creates the conversation object and restores its internal state.
        """
        conversation = await self._create_conversation()

        main_state = await self.get_state(ReflexMainState)
        with await main_state.authenticate_user():
            db_conversation: ChatConversation = ChatConversation.get_by_id_and_check(conversation_id)
            conversation._conversation_id = conversation_id
            conversation._external_conversation_id = db_conversation.external_conversation_id

            conversation_service = ChatConversationService()
            conversation.chat_messages = conversation_service.get_messages_of_conversation(
                conversation_id
            )

        self._conversation = conversation

    async def _after_conversation_updated(self) -> rx.event.EventSpec | None:
        """Refresh sidebar conversations and update URL after a message is sent."""
        async with self:
            history_state = await self.get_state(HistoryState)
            await history_state.load_conversations()

            if self._conversation and self._conversation._conversation_id:
                from ..rag_chat.chat_history_sidebar_state import ChatHistorySidebarState

                sidebar_state = await self.get_state(ChatHistorySidebarState)
                sidebar_state.active_conversation_id = self._conversation._conversation_id

        if self._conversation and self._conversation._conversation_id:
            conversation_id = self._conversation._conversation_id
            return rx.call_script(
                f'window.history.replaceState({{}}, "", "/ai-expert/chat/{conversation_id}")'
            )
        return None

    async def _load_resource(self, resource_id: str) -> None:
        """Load a RAG resource and update UI state."""
        rag_resource = RagResource.from_resource_model_id(resource_id)

        if self._rag_resource and self._rag_resource.get_id() != rag_resource.get_id():
            self.clear_chat()

        self.subtitle = rag_resource.resource_model.name
        self._rag_resource = rag_resource

        app_config_state = await self.get_state(AiExpertConfigState)
        config: AiExpertChatConfig = await app_config_state.get_config()
        self.placeholder_text = config.placeholder_text

    async def load_resource_from_url(self) -> None:
        """Handle page load for /ai-expert/[document_id] route.

        Always starts a fresh conversation for the given document.
        """
        document_id = self.document_id if hasattr(self, "document_id") else None

        if not document_id:
            return None

        rag_resource = RagResource.from_document_or_resource_id_and_check(document_id)

        if not rag_resource:
            self.clear_chat()
            return None

        # Always start a new conversation when navigating to this page
        self.clear_chat()

        self.subtitle = rag_resource.resource_model.name
        self._rag_resource = rag_resource

        # Load placeholder text from config
        app_config_state = await self.get_state(AiExpertConfigState)
        config: AiExpertChatConfig = await app_config_state.get_config()
        self.placeholder_text = config.placeholder_text

    @rx.event
    async def load_conversation_from_url(self) -> None:
        """Handle page load for /ai-expert/chat/[conversation_id] route.

        Loads the conversation and its associated resource from the database.
        """
        conversation_id = self.conversation_id if hasattr(self, "conversation_id") else None

        if not conversation_id:
            return

        if self._conversation and self._conversation._conversation_id == conversation_id:
            return

        try:
            main_state = await self.get_state(ReflexMainState)
            with await main_state.authenticate_user():
                db_conversation: ChatConversation = ChatConversation.get_by_id_and_check(
                    conversation_id
                )
                resource_id = db_conversation.configuration.get(
                    AiExpertChatConversation.RESOURCE_ID_CONFIG_KEY
                )

            if resource_id:
                await self._load_resource(resource_id)

            await self.load_conversation(conversation_id)
        except Exception:
            self.clear_chat()
            return rx.redirect("/ai-expert")

        from ..rag_chat.chat_history_sidebar_state import ChatHistorySidebarState

        sidebar_state = await self.get_state(ChatHistorySidebarState)
        sidebar_state.active_conversation_id = conversation_id

    @rx.event
    async def open_current_resource_file(self):
        """Open the current resource file."""
        if self._rag_resource:
            return await self.open_document_from_resource(self._rag_resource.get_id())
        return None

    async def get_current_resource_model(self) -> ResourceModel | None:
        """Get the current RAG resource model."""
        if self._rag_resource:
            return self._rag_resource.resource_model
        return None
