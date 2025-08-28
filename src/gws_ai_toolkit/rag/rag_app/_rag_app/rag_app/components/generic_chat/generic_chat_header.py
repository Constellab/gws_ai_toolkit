import reflex as rx

from .chat_config import ChatConfig


def generic_chat_header(config: ChatConfig) -> rx.Component:
    """Generic header component - uses chat page style"""

    return rx.hstack(
        rx.vstack(
            rx.heading(config.state.title, size="6"),
            rx.cond(
                config.state.subtitle,
                rx.text(config.state.subtitle, size="2"),
            ),
            spacing="0"
        ),
        rx.spacer(),

        config.header_buttons() if config.header_buttons else None,
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
