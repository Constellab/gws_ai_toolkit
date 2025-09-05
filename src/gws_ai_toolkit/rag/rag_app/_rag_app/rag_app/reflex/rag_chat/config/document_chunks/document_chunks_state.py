from typing import List

import reflex as rx
from gws_core import AuthenticateUser, Logger

from gws_ai_toolkit.rag.common.rag_models import RagChunk

from ..rag_config_state import RagConfigState


class DocumentChunksState(rx.State):
    """State for managing document chunks dialog and operations."""

    # Chunk loading state
    chunks_dialog_open: bool = False
    chunks: List[RagChunk] = []
    chunks_loading: bool = False
    chunks_page: int = 1
    chunks_per_page: int = 10

    # View mode toggle
    view_as_raw: bool = False

    # Selected resource info (passed from parent)
    selected_dataset_id: str = ""
    selected_document_id: str = ""

    def open_chunks_dialog(self, dataset_id: str, document_id: str):
        """Open the chunks dialog and set resource info."""
        self.chunks_dialog_open = True
        self.selected_dataset_id = dataset_id
        self.selected_document_id = document_id

    def close_chunks_dialog(self):
        """Close the chunks dialog."""
        self.chunks_dialog_open = False
        self.chunks = []
        self.chunks_page = 1
        self.view_as_raw = False
        self.selected_dataset_id = ""
        self.selected_document_id = ""

    def set_chunks_dialog_open(self, open: bool):
        """Set the chunks dialog open state."""
        if not open:
            self.close_chunks_dialog()
        else:
            self.chunks_dialog_open = open

    def toggle_raw_view(self):
        """Toggle between markdown and raw text view."""
        self.view_as_raw = not self.view_as_raw

    @rx.event(background=True)
    async def load_chunks(self, page: int = 1):
        """Load chunks for the current resource."""
        if not self.selected_dataset_id or not self.selected_document_id:
            return

        config_state: RagConfigState
        async with self:
            self.chunks_loading = True
            self.chunks_page = page
            config_state = await RagConfigState.get_instance(self)

        try:
            rag_app_service = await config_state.get_dataset_rag_app_service()

            if rag_app_service:
                with AuthenticateUser(await config_state.get_and_check_current_user()):
                    rag_service = rag_app_service.get_rag_service()

                    # Load chunks using get_document_chunks method
                    chunks = rag_service.get_document_chunks(
                        self.selected_dataset_id,
                        self.selected_document_id,
                        None,
                        page,
                        self.chunks_per_page
                    )

                    if len(chunks) == 0:
                        return rx.toast.info("No more chunks to load.", duration=2000)

                    async with self:
                        if page == 1:
                            self.chunks = chunks
                        else:
                            self.chunks.extend(chunks)

        except Exception as e:
            Logger.log_exception_stack_trace(e)
            return rx.toast.error(f"Failed to load chunks: {e}", duration=3000)
        finally:
            async with self:
                self.chunks_loading = False

    @rx.event(background=True)
    async def load_next_chunks_page(self):
        """Load the next page of chunks."""
        return DocumentChunksState.load_chunks(self.chunks_page + 1)
