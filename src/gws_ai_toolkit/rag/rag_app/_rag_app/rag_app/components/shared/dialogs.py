import reflex as rx

from ...states.config_state import ConfigState


def sync_all_dialog() -> rx.Component:
    """Confirmation dialog for syncing all resources."""
    return rx.dialog.root(
        rx.dialog.content(
            rx.dialog.title("Sync All Resources"),
            rx.dialog.description(
                "Are you sure you want to sync all resources to the RAG platform? "
                "This will sync only the resources that are not synced yet."
            ),
            rx.hstack(
                rx.dialog.close(
                    rx.button(
                        "Cancel",
                        variant="outline",
                        on_click=ConfigState.hide_sync_all_confirm,
                    )
                ),
                rx.dialog.close(
                    rx.button(
                        "Yes, Sync All",
                        color_scheme="blue",
                        on_click=ConfigState.start_sync_all,
                    )
                ),
                spacing="2",
                justify="end",
            ),
        ),
        open=ConfigState.show_sync_all_dialog,
    )


def unsync_all_dialog() -> rx.Component:
    """Confirmation dialog for unsyncing all resources."""
    return rx.dialog.root(
        rx.dialog.content(
            rx.dialog.title("Unsync All Resources"),
            rx.dialog.description(
                "Are you sure you want to unsync all resources from the RAG platform? "
                "This will remove all synced resources from the RAG system."
            ),
            rx.hstack(
                rx.dialog.close(
                    rx.button(
                        "Cancel",
                        variant="outline",
                        on_click=ConfigState.hide_unsync_all_confirm,
                    )
                ),
                rx.dialog.close(
                    rx.button(
                        "Yes, Unsync All",
                        color_scheme="red",
                        on_click=ConfigState.start_unsync_all,
                    )
                ),
                spacing="2",
                justify="end",
            ),
        ),
        open=ConfigState.show_unsync_all_dialog,
    )


def delete_expired_dialog() -> rx.Component:
    """Confirmation dialog for deleting expired documents."""
    return rx.dialog.root(
        rx.dialog.content(
            rx.dialog.title("Delete Expired Documents"),
            rx.dialog.description(
                "Are you sure you want to delete expired documents from the RAG platform? "
                "These documents were deleted from DataHub and are no longer synced."
            ),
            rx.hstack(
                rx.dialog.close(
                    rx.button(
                        "Cancel",
                        variant="outline",
                        on_click=ConfigState.hide_delete_expired_confirm,
                    )
                ),
                rx.dialog.close(
                    rx.button(
                        "Yes, Delete",
                        color_scheme="orange",
                        on_click=ConfigState.start_delete_expired,
                    )
                ),
                spacing="2",
                justify="end",
            ),
        ),
        open=ConfigState.show_delete_expired_dialog,
    )


def confirmation_dialogs() -> rx.Component:
    """All confirmation dialogs."""
    return rx.fragment(
        sync_all_dialog(),
        unsync_all_dialog(),
        delete_expired_dialog(),
    )
