"""State management for document browser in AI Expert mode."""

import reflex as rx
from gws_ai_toolkit.models.chat.chat_conversation_service import ChatConversationService
from gws_ai_toolkit.rag.common.rag_models import RagChatSource

from ..core.app_config_state import AppConfigState


class DocumentBrowserState(rx.State):
    """State for managing document browser functionality.

    This state handles loading and displaying available documents that can be
    opened in AI Expert mode. Documents are retrieved from chat history.

    Attributes:
        documents: List of available documents from chat history
        is_loading: Whether documents are currently being loaded
    """

    documents: list[RagChatSource] = []
    is_loading: bool = False

    @rx.var
    def has_documents(self) -> bool:
        """Check if there are any documents available.

        Returns:
            bool: True if documents list is not empty
        """
        return len(self.documents) > 0

    async def load_documents(self) -> None:
        """Load available documents from chat history.

        Retrieves the first 20 documents that have been referenced in chat
        conversations for the current chat app.
        """
        self.is_loading = True

        try:
            # Get chat app name from config
            app_config_state = await AppConfigState.get_instance(self)
            chat_app_name = await app_config_state.get_chat_app_name()

            # Get documents from chat history
            service = ChatConversationService()
            page_dto = service.get_message_sources_by_chat_app(
                chat_app_name=chat_app_name,
                page=0,
                number_of_items_per_page=20,
            )

            # Convert to RagChatSource objects
            self.documents = page_dto.objects
        finally:
            self.is_loading = False
