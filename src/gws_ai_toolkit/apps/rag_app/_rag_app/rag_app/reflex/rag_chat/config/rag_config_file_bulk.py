import reflex as rx

from .delete_expired_documents_dialog.delete_expired_documents_dialog_component import (
    delete_expired_documents_dialog,
)
from .delete_expired_documents_dialog.delete_expired_documents_dialog_state import (
    DeleteExpiredDocumentsDialogState,
)
from .sync_all_resources_dialog.sync_all_resources_dialog_component import sync_all_resources_dialog
from .sync_all_resources_dialog.sync_all_resources_dialog_state import SyncAllResourcesDialogState
from .unsync_all_resources_dialog.unsync_all_resources_dialog_component import (
    unsync_all_resources_dialog,
)
from .unsync_all_resources_dialog.unsync_all_resources_dialog_state import (
    UnsyncAllResourcesDialogState,
)


def bulk_action_buttons() -> rx.Component:
    """Buttons for bulk sync/unsync operations."""
    return rx.hstack(
        rx.dialog.root(
            rx.dialog.trigger(
                rx.button(
                    rx.icon("refresh-cw", size=16),
                    "Sync All Resources",
                    on_click=SyncAllResourcesDialogState.open_dialog,
                )
            ),
            rx.dialog.content(
                sync_all_resources_dialog(),
            ),
            on_open_change=SyncAllResourcesDialogState.on_sync_resource_dialog_event,
            open=SyncAllResourcesDialogState.resources_to_sync_dialog_opened,
        ),
        rx.dialog.root(
            rx.dialog.trigger(
                rx.button(
                    rx.icon("refresh-cw-off", size=16),
                    "Unsync All Resources",
                    color_scheme="red",
                    on_click=UnsyncAllResourcesDialogState.open_dialog,
                )
            ),
            rx.dialog.content(
                unsync_all_resources_dialog(),
            ),
            on_open_change=UnsyncAllResourcesDialogState.on_unsync_resource_dialog_event,
            open=UnsyncAllResourcesDialogState.resources_to_unsync_dialog_opened,
        ),
        rx.dialog.root(
            rx.dialog.trigger(
                rx.button(
                    rx.icon("trash", size=16),
                    "Delete Expired Documents",
                    color_scheme="orange",
                    variant="outline",
                    on_click=DeleteExpiredDocumentsDialogState.open_dialog,
                )
            ),
            rx.dialog.content(
                delete_expired_documents_dialog(),
            ),
            on_open_change=DeleteExpiredDocumentsDialogState.on_delete_documents_dialog_event,
            open=DeleteExpiredDocumentsDialogState.documents_to_delete_dialog_opened,
        ),
        spacing="3",
        wrap="wrap",
    )


def rag_config_file_bulk() -> rx.Component:
    """Main sync controls component."""
    return rx.vstack(
        rx.heading("Configuration", size="6"),
        bulk_action_buttons(),
    )
