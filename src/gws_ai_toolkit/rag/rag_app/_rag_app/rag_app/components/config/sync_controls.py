import reflex as rx
from ...states.config_state import ConfigState


def bulk_action_buttons() -> rx.Component:
    """Buttons for bulk sync/unsync operations."""
    return rx.hstack(
        rx.button(
            rx.icon("sync", size=16),
            "Sync All Resources",
            on_click=ConfigState.show_sync_all_confirm,
            color_scheme="blue",
            disabled=ConfigState.is_syncing | ConfigState.is_unsyncing | ConfigState.is_deleting,
        ),
        rx.button(
            rx.icon("x-circle", size=16),
            "Unsync All Resources", 
            on_click=ConfigState.show_unsync_all_confirm,
            color_scheme="red",
            variant="outline",
            disabled=ConfigState.is_syncing | ConfigState.is_unsyncing | ConfigState.is_deleting,
        ),
        rx.button(
            rx.icon("trash", size=16),
            "Delete Expired Documents",
            on_click=ConfigState.show_delete_expired_confirm,
            color_scheme="orange",
            variant="outline",
            disabled=ConfigState.is_syncing | ConfigState.is_unsyncing | ConfigState.is_deleting,
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
                        disabled=ConfigState.is_syncing,
                    ),
                    rx.button(
                        rx.icon("trash-2", size=16),
                        "Delete from RAG",
                        on_click=ConfigState.delete_selected_resource,
                        size="2",
                        color_scheme="red",
                        variant="outline",
                        disabled=ConfigState.is_deleting,
                    ),
                    spacing="2",
                ),
                rx.button(
                    rx.icon("upload", size=16),
                    "Send to RAG",
                    on_click=ConfigState.sync_selected_resource,
                    size="2",
                    color_scheme="blue",
                    disabled=ConfigState.is_syncing,
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