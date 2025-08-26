import reflex as rx

from .delete_expired_documents_dialog_state import \
    DeleteExpiredDocumentsDialogState


def _delete_pending() -> rx.Component:
    """Content for the delete pending state."""
    return rx.cond(
        DeleteExpiredDocumentsDialogState.count_documents_to_delete > 0, rx.vstack(
            rx.text(
                f"Are you sure you want to delete {DeleteExpiredDocumentsDialogState.count_documents_to_delete} expired documents?",
                size="3"),
            rx.text(
                "Those documents were deleted from DataHub and are still synced with the RAG platform.", size="2",
                color="gray.600"),
            rx.accordion.root(
                rx.accordion.item(
                    header="Show documents to delete", content=rx.vstack(
                        rx.foreach(
                            DeleteExpiredDocumentsDialogState.documents_info, lambda document: rx.text(
                                f"• {document}", size="2")),
                        padding_top="2"),),
                width="100%", variant="outline",),
            rx.hstack(
                rx.button(
                    "Delete documents", size="3", color_scheme="red",
                    on_click=DeleteExpiredDocumentsDialogState.delete_expired_documents_from_rag),
                rx.button("Cancel", size="3", on_click=DeleteExpiredDocumentsDialogState.close_dialog),
                spacing="2"),
            spacing="3"),
        rx.vstack(
            rx.text("No expired documents to delete.", size="3"),
            rx.button("Close", size="3", on_click=DeleteExpiredDocumentsDialogState.close_dialog),
            spacing="3"))


def _delete_running() -> rx.Component:
    """Content for the delete running state."""
    return rx.vstack(
        rx.text("Deleting expired documents..."),
        rx.hstack(
            rx.progress(value=DeleteExpiredDocumentsDialogState.get_documents_delete_progress_percent, flex='1'),
            rx.text(
                f"{DeleteExpiredDocumentsDialogState.delete_documents_progress}/{DeleteExpiredDocumentsDialogState.count_documents_to_delete}"),
            align_items="center", width='100%'),
        width='100%')


def _delete_done() -> rx.Component:
    """Content for the delete done state."""
    return rx.vstack(
        rx.text("Deletion finished", size="3"),
        rx.foreach(
            DeleteExpiredDocumentsDialogState.delete_errors, lambda error: rx.text(
                error, size="2", color="red.600")),
        rx.button("Close", size="3", on_click=DeleteExpiredDocumentsDialogState.close_dialog),
        spacing="3")


def _dialog_content() -> rx.Component:
    """Content for the delete expired documents dialog."""
    return rx.match(
        DeleteExpiredDocumentsDialogState.documents_delete_status,
        ("pending", _delete_pending()),
        ("running", _delete_running()),
        ("done", _delete_done()),
    )


def delete_expired_documents_dialog() -> rx.Component:
    """Dialog for deleting expired documents."""
    return rx.vstack(
        rx.dialog.title("Delete Expired Documents from RAG"),
        rx.cond(DeleteExpiredDocumentsDialogState.has_loaded_documents_to_delete,
                _dialog_content(),
                rx.hstack(
                    rx.spinner(),
                    rx.text("Loading expired documents...", size="3"),
                    align_items="center",
                ),
                ),
    )
