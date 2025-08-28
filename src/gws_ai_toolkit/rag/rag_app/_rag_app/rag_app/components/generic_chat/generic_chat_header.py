import reflex as rx

from .chat_config import ChatConfig


def generic_chat_header(config: ChatConfig) -> rx.Component:
    """Generic header component - uses chat page style"""

    return rx.hstack(
        rx.heading(config.state.title, size="6"),
        rx.spacer(),
        rx.button(
            rx.icon("refresh-cw", size=16),
            config.state.clear_button_text,
            on_click=config.state.clear_chat,
            variant="outline",
            size="2",
            cursor="pointer",
        ),
        width="100%",
        align="center",
    )
