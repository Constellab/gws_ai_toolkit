import reflex as rx

from .sync_all_resources_dialog_state import SyncAllResourcesDialogState


def _sync_pending() -> rx.Component:
    """Content for the sync pending state."""
    return rx.vstack(

        rx.text(
            f"Are you sure you want to sync all {SyncAllResourcesDialogState.count_resources_to_sync} resources?",
            size="3"
        ),
        rx.hstack(
            rx.button(
                "Sync resources",
                size="3",
                on_click=SyncAllResourcesDialogState.sync_resources_to_rag),
            rx.button("Cancel", size="3",
                      on_click=SyncAllResourcesDialogState.close_dialog),
        )
    )


def _sync_running() -> rx.Component:
    """Content for the sync running state."""
    return rx.vstack(
        rx.text("Syncing resources..."),
        rx.hstack(
            rx.progress(value=SyncAllResourcesDialogState.get_resource_sync_progress_percent, flex='1'),
            rx.text(
                f"{SyncAllResourcesDialogState.sync_resource_progress}/{SyncAllResourcesDialogState.count_resources_to_sync}"),
            align_items="center", width='100%'),
        width='100%')


def _sync_done() -> rx.Component:
    """Content for the sync done state."""
    return rx.vstack(
        rx.text("Sync finished", size="3"),
        rx.foreach(SyncAllResourcesDialogState.sync_errors, lambda error: rx.text(error, size="3")),
        rx.button("Close", size="3", on_click=SyncAllResourcesDialogState.close_dialog)
    )


def _dialog_content() -> rx.Component:
    """Content for the sync all resources dialog."""
    return rx.match(
        SyncAllResourcesDialogState.resources_sync_status,
        ("pending", _sync_pending()),
        ("running", _sync_running()),
        ("done", _sync_done()),
    )


def sync_all_resources_dialog() -> rx.Component:
    """Dialog for syncing all resources."""
    return rx.vstack(
        rx.dialog.title("Sync All Resources"),
        rx.cond(SyncAllResourcesDialogState.has_loaded_resources_to_sync,
                _dialog_content(),
                rx.hstack(
                    rx.spinner(),
                    rx.text("Loading resources...", size="3"),
                    align_items="center",
                ),
                ),
    )
