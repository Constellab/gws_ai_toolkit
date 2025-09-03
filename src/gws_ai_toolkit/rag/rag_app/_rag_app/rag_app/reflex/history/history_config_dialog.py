import reflex as rx

from ..chat_base.chat_state_base import ChatStateBase


def history_config_dialog(state: ChatStateBase) -> rx.Component:
    """Configuration dialog component for displaying conversation configuration as JSON."""

    # Check if this is a ReadOnlyChatState with config dialog support
    has_config_dialog = (
        hasattr(state, 'show_config_dialog') and
        hasattr(state, 'config_json_string') and
        hasattr(state, 'close_config_dialog')
    )

    if not has_config_dialog:
        return rx.fragment()  # Return empty fragment if not supported

    return rx.dialog.root(
        rx.dialog.content(
            rx.dialog.title(
                "Conversation Configuration",
                size="5",
                margin_bottom="16px"
            ),
            rx.dialog.description(
                "This shows the configuration that was used for this conversation.",
                size="2",
                margin_bottom="20px",
                color=rx.color("gray", 11)
            ),

            # JSON display area
            rx.box(
                rx.code_block(
                    state.config_json_string,
                    language="json",
                    theme="light",
                    show_line_numbers=True,
                    can_copy=True,
                    width="100%",
                ),
                width="100%",
                max_height="400px",
                overflow="auto",
                border=f"1px solid {rx.color('gray', 6)}",
                border_radius="8px",
                padding="12px",
                background_color=rx.color("gray", 1),
                margin_bottom="20px"
            ),

            # Dialog buttons
            rx.hstack(
                rx.dialog.close(
                    rx.button(
                        "Close",
                        variant="outline",
                        on_click=state.close_config_dialog
                    ),
                ),
                justify="end",
                width="100%"
            ),

            max_width="600px",
            width="90vw",
            padding="24px"
        ),
        open=state.show_config_dialog
    )
