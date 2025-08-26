import reflex as rx

from ...states.chat_state import ChatState
from .message_list import message_list


def chat_input() -> rx.Component:
    """Chat input component with send functionality."""
    return rx.form(
        rx.hstack(
            rx.input(
                placeholder="Ask something...",
                name="message",
                flex="1",
                disabled=ChatState.is_streaming,
            ),
            rx.button(
                rx.icon("send", size=16),
                type="submit",
                disabled=ChatState.is_streaming,
                color_scheme="blue",
                cursor="pointer",
            ),
            width="100%",
            spacing="2",
        ),
        on_submit=ChatState.add_user_message,
        reset_on_submit=True,
    )


def chat_header() -> rx.Component:
    """Chat header with title and controls."""
    return rx.hstack(
        rx.heading("AI Chat", size="6"),
        rx.spacer(),
        rx.button(
            rx.icon("refresh-cw", size=16),
            "Clear History",
            on_click=ChatState.clear_chat,
            variant="outline",
            size="2",
            cursor="pointer",
        ),
        width="100%",
        align="center",
    )


def chat_interface() -> rx.Component:
    """Main chat interface component."""
    return rx.vstack(
        chat_header(),
        message_list(),
        chat_input(),
        width="100%",
        max_width="800px",
        margin="auto",
        flex="1",
        padding_top="1em",
        padding_bottom="1em",
    )
