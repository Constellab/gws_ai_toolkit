import reflex as rx

from .unsync_all_resources_dialog_state import UnsyncAllResourcesDialogState


def _unsync_pending() -> rx.Component:
    """Content for the unsync pending state."""
    return rx.vstack(

        rx.text(
            f"Are you sure you want to unsync all {UnsyncAllResourcesDialogState.count_resources_to_unsync} resources?",
            size="3"
        ),
        rx.hstack(
            rx.button(
                "Unsync resources",
                size="3",
                on_click=UnsyncAllResourcesDialogState.unsync_resources_from_rag),
            rx.button("Cancel", size="3",
                      on_click=UnsyncAllResourcesDialogState.close_dialog),
        )
    )


def _unsync_running() -> rx.Component:
    """Content for the unsync running state."""
    return rx.vstack(
        rx.text("Unsyncing resources..."),
        rx.hstack(
            rx.progress(value=UnsyncAllResourcesDialogState.get_resource_unsync_progress_percent, flex='1'),
            rx.text(
                f"{UnsyncAllResourcesDialogState.unsync_resource_progress}/{UnsyncAllResourcesDialogState.count_resources_to_unsync}"),
            align_items="center", width='100%'),
        width='100%')


def _unsync_done() -> rx.Component:
    """Content for the unsync done state."""
    return rx.vstack(
        rx.text("Unsync finished", size="3"),
        rx.foreach(UnsyncAllResourcesDialogState.unsync_errors, lambda error: rx.text(error, size="3")),
        rx.button("Close", size="3", on_click=UnsyncAllResourcesDialogState.close_dialog)
    )


def _dialog_content() -> rx.Component:
    """Content for the unsync all resources dialog."""
    return rx.match(
        UnsyncAllResourcesDialogState.resources_unsync_status,
        ("pending", _unsync_pending()),
        ("running", _unsync_running()),
        ("done", _unsync_done()),
    )


def unsync_all_resources_dialog() -> rx.Component:
    """Dialog for unsyncing all resources."""
    return rx.vstack(
        rx.dialog.title("Unsync All Resources"),
        rx.cond(UnsyncAllResourcesDialogState.has_loaded_resources_to_unsync,
                _dialog_content(),
                rx.hstack(
                    rx.spinner(),
                    rx.text("Loading resources...", size="3"),
                    align_items="center",
                ),
                ),
    )
