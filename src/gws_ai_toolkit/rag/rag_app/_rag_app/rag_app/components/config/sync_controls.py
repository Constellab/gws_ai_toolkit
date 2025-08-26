import reflex as rx
from gws_ai_toolkit.rag.rag_app._rag_app.rag_app.components.config.delete_expired_documents_dialog.delete_expired_documents_dialog_component import \
    delete_expired_documents_dialog
from gws_ai_toolkit.rag.rag_app._rag_app.rag_app.components.config.delete_expired_documents_dialog.delete_expired_documents_dialog_state import \
    DeleteExpiredDocumentsDialogState
from gws_ai_toolkit.rag.rag_app._rag_app.rag_app.components.config.sync_all_resources_dialog.sync_all_resources_dialog_component import \
    sync_all_resources_dialog
from gws_ai_toolkit.rag.rag_app._rag_app.rag_app.components.config.sync_all_resources_dialog.sync_all_resources_dialog_state import \
    SyncAllResourcesDialogState
from gws_ai_toolkit.rag.rag_app._rag_app.rag_app.components.config.unsync_all_resources_dialog.unsync_all_resources_dialog_component import \
    unsync_all_resources_dialog
from gws_ai_toolkit.rag.rag_app._rag_app.rag_app.components.config.unsync_all_resources_dialog.unsync_all_resources_dialog_state import \
    UnsyncAllResourcesDialogState
from gws_ai_toolkit.rag.rag_app._rag_app.rag_app.states.config_state import \
    ConfigState


def bulk_action_buttons() -> rx.Component:
    """Buttons for bulk sync/unsync operations."""
    return rx.hstack(
        rx.dialog.root(
            rx.dialog.trigger(
                rx.button(
                    rx.icon("sync", size=16),
                    "Sync All Resources",
                    color_scheme="blue",
                    on_click=SyncAllResourcesDialogState.open_dialog,
                )
            ),
            rx.dialog.content(
                sync_all_resources_dialog(),
            ),
            on_open_change=SyncAllResourcesDialogState.on_sync_resource_dialog_event,
            open=SyncAllResourcesDialogState.resources_to_sync_dialog_opened
        ),
        rx.dialog.root(
            rx.dialog.trigger(
                rx.button(
                    rx.icon("x-circle", size=16),
                    "Unsync All Resources",
                    color_scheme="red",
                    on_click=UnsyncAllResourcesDialogState.open_dialog,
                )
            ),
            rx.dialog.content(
                unsync_all_resources_dialog(),
            ),
            on_open_change=UnsyncAllResourcesDialogState.on_unsync_resource_dialog_event,
            open=UnsyncAllResourcesDialogState.resources_to_unsync_dialog_opened
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
            open=DeleteExpiredDocumentsDialogState.documents_to_delete_dialog_opened
        ),
        spacing="3",
        wrap="wrap",
    )


def resource_actions() -> rx.Component:
    """Action buttons for selected resource."""
    return rx.cond(
        ConfigState.selected_resource_id,
        rx.vstack(
            rx.text(
                ConfigState.get_selected_resource_info,
                font_weight="medium",
                color=rx.cond(
                    ConfigState.selected_resource_synced,
                    "green.600",
                    "orange.600"
                )
            ),
            rx.cond(
                ConfigState.selected_resource_synced,
                rx.hstack(
                    rx.button(
                        rx.icon("refresh-cw", size=16),
                        "Resync",
                        on_click=ConfigState.sync_selected_resource,
                        size="2",
                    ),
                    rx.button(
                        rx.icon("trash-2", size=16),
                        "Delete from RAG",
                        on_click=ConfigState.delete_selected_resource,
                        size="2",
                        color_scheme="red",
                        variant="outline",
                    ),
                    spacing="2",
                ),
                rx.button(
                    rx.icon("upload", size=16),
                    "Send to RAG",
                    on_click=ConfigState.sync_selected_resource,
                    size="2",
                    color_scheme="blue",
                ),
            ),
            spacing="3",
            align="start",
        )
    )


def sync_controls() -> rx.Component:
    """Main sync controls component."""
    return rx.vstack(
        rx.heading("Configuration", size="6"),
        bulk_action_buttons(),
        rx.divider(),
        rx.text(
            "Search and select a resource to view its sync status and send it to the RAG platform.",
            font_size="sm",
            color="gray.600",
        ),
        # Resource selection would go here
        # resource_selector(),
        resource_actions(),
        spacing="4",
        align="start",
        width="100%",
    )
