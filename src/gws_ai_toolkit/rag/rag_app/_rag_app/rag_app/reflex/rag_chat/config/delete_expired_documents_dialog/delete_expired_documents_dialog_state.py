from typing import List, Literal

import reflex as rx
from gws_core import AuthenticateUser, Logger, User

from gws_ai_toolkit.rag.common.rag_models import RagDocument

from ..rag_config_state import RagConfigState


class DeleteExpiredDocumentsDialogState(rx.State):
    """State management for the delete expired documents dialog functionality."""

    documents_to_delete: List[RagDocument] = []
    documents_to_delete_dialog_opened: bool = False
    delete_documents_progress: int = -1
    delete_errors: List[str] = []

    @rx.var
    def count_documents_to_delete(self) -> int:
        return len(self.documents_to_delete)

    @rx.var(cache=False)
    def has_loaded_documents_to_delete(self) -> bool:
        return self.documents_to_delete is not None

    @rx.var
    def documents_info(self) -> List[str]:
        return [f"{doc.name} ({doc.id})" for doc in self.documents_to_delete]

    @rx.var
    def documents_delete_status(self) -> Literal['pending', 'running', 'done']:
        if self.delete_documents_progress < 0:
            return "pending"
        elif self.delete_documents_progress < self.count_documents_to_delete:
            return "running"
        return "done"

    @rx.var
    def get_documents_delete_progress_percent(self) -> int:
        if self.count_documents_to_delete <= 0:
            return 0
        return int(self.delete_documents_progress / self.count_documents_to_delete * 100)

    @rx.event
    def open_dialog(self):
        self.documents_to_delete_dialog_opened = True

    @rx.event
    def close_dialog(self):
        """Close the documents to delete dialog."""
        self.documents_to_delete_dialog_opened = False

    @rx.event(background=True)
    async def on_delete_documents_dialog_event(self, opened: bool):
        """Handle dialog open event to load documents."""
        if opened:
            await self.load_documents_to_delete()

    async def load_documents_to_delete(self):
        """Load documents to delete."""
        config_state: RagConfigState
        async with self:
            self.documents_to_delete = []
            self.delete_documents_progress = -1
            config_state = await RagConfigState.get_instance(self)

        rag_service = await config_state.get_dataset_rag_app_service()

        documents_to_delete = rag_service.get_rag_documents_to_delete()
        async with self:
            self.documents_to_delete = documents_to_delete

    @rx.event(background=True)
    async def delete_expired_documents_from_rag(self):
        config_state: RagConfigState
        user: User
        async with self:
            self.delete_documents_progress = 0
            self.delete_errors = []
            config_state = await RagConfigState.get_instance(self)
            user = await config_state.get_and_check_current_user()

        rag_service = await config_state.get_dataset_rag_app_service()

        for document in self.documents_to_delete:
            try:
                with AuthenticateUser(user):
                    rag_service.delete_rag_document(document.id)

            except Exception as e:
                Logger.error(f"Error deleting document '{document.name}' {document.id}: {e}")
                async with self:
                    self.delete_errors.append(
                        f"Error deleting document '{document.name}' {document.id}: {e}")

            async with self:
                self.delete_documents_progress += 1
