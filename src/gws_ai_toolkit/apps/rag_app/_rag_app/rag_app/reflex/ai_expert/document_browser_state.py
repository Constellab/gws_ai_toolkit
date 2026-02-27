"""State management for document browser in AI Expert mode."""

import reflex as rx
from gws_ai_toolkit.models.chat.chat_conversation_service import ChatConversationService
from gws_ai_toolkit.rag.common.rag_models import RagChatSource
from gws_core import BaseModelDTO
from gws_reflex_main import ReflexMainState

from ..core.app_config_state import AppConfigState


def _get_extension_label(filename: str) -> str:
    """Extract uppercase 3-letter extension label from a filename."""
    ext = ""
    if "." in filename:
        ext = filename.rsplit(".", 1)[-1].lower()
    return ext[:3].upper() if ext else "FILE"


class DocumentBrowserInfo(BaseModelDTO):
    """Frontend DTO for document browser items."""

    document_id: str
    document_name: str
    extension: str


class DocumentBrowserState(rx.State):
    """State for managing document browser functionality.

    This state handles loading and displaying available documents that can be
    opened in AI Expert mode. Documents are retrieved from chat history.

    Attributes:
        documents: List of available documents from chat history
        is_loading: Whether documents are currently being loaded
    """

    documents: list[DocumentBrowserInfo] = []
    is_loading: bool = False

    @rx.var
    def has_documents(self) -> bool:
        """Check if there are any documents available.

        Returns:
            bool: True if documents list is not empty
        """
        return len(self.documents) > 0

    @staticmethod
    def _to_browser_info(source: RagChatSource) -> DocumentBrowserInfo:
        """Convert a RagChatSource to a DocumentBrowserInfo."""
        return DocumentBrowserInfo(
            document_id=source.document_id,
            document_name=source.document_name,
            extension=_get_extension_label(source.document_name),
        )

    @rx.event(background=True)
    async def load_documents(self) -> None:
        """Load available documents from chat history.

        Retrieves the first 20 documents that have been referenced in chat
        conversations for the current chat app.
        """

        main_state: ReflexMainState
        app_config_state: AppConfigState

        async with self:
            self.is_loading = True
            main_state = await self.get_state(ReflexMainState)
            app_config_state = await AppConfigState.get_instance(self)

        try:
            # Get chat app name from config
            chat_app_name = await app_config_state.get_chat_app_name()

            # Get documents from chat history
            service = ChatConversationService()
            with await main_state.authenticate_user():
                page_dto = service.get_message_sources_by_chat_app(
                    chat_app_name=chat_app_name,
                    page=0,
                    number_of_items_per_page=20,
                )

            async with self:
                self.documents = [
                    self._to_browser_info(source) for source in page_dto.objects
                ]
        finally:
            async with self:
                self.is_loading = False
