import reflex as rx

from .chat_config import ChatStateBase


def generic_chat_header(state: ChatStateBase) -> rx.Component:
    """Generic header component - uses chat page style"""

    # TODO FIX
    header_buttons = []
    # header_buttons = config.header_buttons() if config.header_buttons else []

    return rx.vstack(

        rx.hstack(
            rx.vstack(
                rx.heading(state.title, size="6"),
                rx.cond(
                    state.subtitle,
                    rx.text(state.subtitle, size="2"),
                ),
                spacing="0"
            ),
            rx.spacer(),
            *header_buttons,
            rx.button(
                rx.icon("refresh-cw", size=16),
                state.clear_button_text,
                on_click=state.clear_chat,
                variant="outline",
                size="2",
                cursor="pointer",
            ),
            width="100%",
            align="center",
        ),
        width="100%"
    )
