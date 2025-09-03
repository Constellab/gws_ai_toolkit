from typing import List

import reflex as rx

from gws_ai_toolkit.rag.rag_app._rag_app.rag_app.components.generic_chat.chat_state_base import \
    ChatStateBase

from .chat_config import ChatConfig


def header_clear_chat_button(state: ChatStateBase) -> rx.Component:
    return rx.button(
        rx.icon("refresh-cw", size=16),
        state.clear_button_text,
        on_click=state.clear_chat,
        variant="outline",
        size="2",
        cursor="pointer",
    )


def generic_chat_header(config: ChatConfig) -> rx.Component:
    """Generic header component - uses chat page style"""

    header_buttons: List[rx.Component] = []
    if config.header_buttons is None:
        # default value
        header_buttons = [header_clear_chat_button(config.state)]
    else:
        header_buttons = config.header_buttons(config.state)

    return rx.vstack(

        rx.hstack(
            rx.vstack(
                rx.heading(config.state.title, size="6"),
                rx.cond(
                    config.state.subtitle,
                    rx.text(config.state.subtitle, size="2"),
                ),
                spacing="0"
            ),
            rx.spacer(),
            *header_buttons,
            width="100%",
            align="center",
        ),
        width="100%"
    )
