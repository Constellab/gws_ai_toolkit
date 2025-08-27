import reflex as rx

from ...states.ai_expert_state import AiExpertState
from .ai_expert_message_list import ai_expert_message_list


def ai_expert_chat_input() -> rx.Component:
    """AI Expert chat input component with send functionality."""
    return rx.form(
        rx.hstack(
            rx.input(
                placeholder="Ask about this document...",
                name="message",
                flex="1",
                disabled=AiExpertState.is_streaming,
            ),
            rx.button(
                rx.icon("send", size=16),
                type="submit",
                disabled=AiExpertState.is_streaming,
                color_scheme="blue",
                cursor="pointer",
            ),
            width="100%",
            spacing="2",
        ),
        on_submit=AiExpertState.add_user_message,
        reset_on_submit=True,
    )


def ai_expert_chat_header() -> rx.Component:
    """AI Expert chat header with title and controls."""
    return rx.hstack(
        rx.vstack(
            rx.heading(AiExpertState.get_document_title, size="6"),
            rx.text(
                "Ask questions about this specific document",
                color="gray.600",
                font_size="sm",
            ),
            align_items="start",
            spacing="1",
        ),
        rx.spacer(),
        rx.hstack(
            rx.link(
                rx.button(
                    rx.icon("arrow-left", size=16),
                    "Back to Chat",
                    variant="outline",
                    size="2",
                    cursor="pointer",
                ),
                href="/",
            ),
            rx.button(
                rx.icon("refresh-cw", size=16),
                "Clear History",
                on_click=AiExpertState.clear_chat,
                variant="outline",
                size="2",
                cursor="pointer",
            ),
            spacing="2",
        ),
        width="100%",
        align="center",
    )


def ai_expert_chat_interface() -> rx.Component:
    """Main AI Expert chat interface component."""
    return rx.vstack(
        ai_expert_chat_header(),
        ai_expert_message_list(),
        ai_expert_chat_input(),
        width="100%",
        max_width="800px",
        margin="auto",
        flex="1",
        padding_top="1em",
        padding_bottom="1em",
    )