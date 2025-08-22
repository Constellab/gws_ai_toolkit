import reflex as rx

from ...states.config_state import ConfigState


def progress_bar() -> rx.Component:
    """Progress bar for long-running operations."""
    return rx.cond(
        ConfigState.is_syncing | ConfigState.is_unsyncing | ConfigState.is_deleting,
        rx.vstack(
            rx.progress(
                value=ConfigState.operation_progress,
                width="100%",
                height="8px",
                color_scheme="blue",
            ),
            rx.text(
                ConfigState.get_operation_status,
                font_size="sm",
                color="gray.600",
            ),
            spacing="2",
            width="100%",
        )
    )


def status_messages() -> rx.Component:
    """Display operation status and error messages."""
    return rx.vstack(
        rx.cond(
            ConfigState.operation_message != "",
            rx.text(ConfigState.operation_message, color="green.600"),
        ),
        rx.cond(
            ConfigState.operation_error != "",
            rx.text(ConfigState.operation_error, color="red.600"),
        ),
        rx.cond(
            (ConfigState.operation_message != "") | (ConfigState.operation_error != ""),
            rx.button(
                "Clear Messages",
                on_click=ConfigState.clear_messages,
                size="2",
                variant="outline",
            ),
        ),
        spacing="3",
        width="100%",
    )


def progress_tracker() -> rx.Component:
    """Main progress tracker component."""
    return rx.vstack(
        progress_bar(),
        status_messages(),
        spacing="4",
        width="100%",
    )
