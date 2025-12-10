import reflex as rx
from gws_ai_toolkit.models.chat.chat_conversation_service import ChatConversationService
from gws_ai_toolkit.models.chat.message.chat_message_source import RagChatSourceFront
from gws_ai_toolkit.rag.common.rag_models import RagChatSource
from gws_reflex_main import ReflexMainState


class SourceDetailState(rx.State):
    """State for managing source detail dialog.

    This state handles loading a ChatMessageSourceModel by ID and displaying
    its details in a dialog. The source is loaded when the dialog opens and
    converted to a RagChatSource DTO for display.

    State Attributes:
        is_dialog_open (bool): Whether the dialog is currently open
        source (RagChatSource | None): The loaded source data as DTO
        is_loading (bool): Whether the source is currently being loaded
    """

    is_dialog_open: bool = False
    source: RagChatSource | None = None
    is_loading: bool = False

    @rx.event(background=True)
    async def open_source_dialog(self, source_id: str | None):
        """Open the dialog and trigger loading of the source.

        Args:
            source_id: The ID of the ChatMessageSourceModel to load
        """
        if not source_id:
            return
        async with self:
            self.is_dialog_open = True
        return await self.load_source(source_id)

    @rx.event
    def close_dialog(self):
        """Close the dialog and clear the source data."""
        self.is_dialog_open = False
        self.source = None

    async def load_source(self, source_id: str):
        """Load the source by ID from the database.

        This method fetches the ChatMessageSourceModel and converts it
        to a RagChatSource DTO for display in the UI.

        Args:
            source_id: The ID of the source to load
        """
        main_state: ReflexMainState
        async with self:
            self.is_loading = True
            self.source = None
            main_state: ReflexMainState = await self.get_state(ReflexMainState)

        try:
            # Get the main state to authenticate user

            with await main_state.authenticate_user():
                # Load the source from database
                chat_service = ChatConversationService()
                source_model = chat_service.get_source_by_id_and_check(source_id)

                # Convert to DTO
                source_dto = source_model.to_rag_dto()

            async with self:
                self.source = source_dto
                self.is_loading = False
        except:
            async with self:
                self.is_dialog_open = False

        finally:
            async with self:
                self.is_loading = False

    @rx.var
    def source_front(self) -> RagChatSourceFront | None:
        """Get the source DTO for front-end use.

        Returns:
            RagChatSource | None: The loaded source DTO or None
        """
        if not self.source:
            return None
        return RagChatSourceFront(
            id=self.source.id,
            document_id=self.source.document_id,
            document_name=self.source.document_name,
        )
