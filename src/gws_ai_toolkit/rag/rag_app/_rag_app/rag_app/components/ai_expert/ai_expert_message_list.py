import reflex as rx

from ...states.ai_expert_state import AiExpertState
from ...states.chat_state import ChatMessage


def ai_expert_message_bubble(message: ChatMessage) -> rx.Component:
    """Display a single chat message with appropriate styling."""
    is_user = message.role == "user"

    return rx.box(
        rx.box(
            rx.text(
                message.content,
                white_space="pre-wrap",
                word_wrap="break-word",
            ),
            background_color=rx.cond(is_user, "blue.500", "gray.100"),
            color=rx.cond(is_user, "white", "black"),
            padding="3",
            border_radius="lg",
            max_width="70%",
            align_self=rx.cond(is_user, "flex-end", "flex-start"),
        ),
        width="100%",
        display="flex",
        justify_content=rx.cond(is_user, "flex-end", "flex-start"),
        margin_bottom="3",
    )


def ai_expert_current_message() -> rx.Component:
    """Display the current streaming message."""
    return rx.cond(
        AiExpertState.current_response_display,
        rx.box(
            rx.box(
                rx.hstack(
                    rx.text(
                        rx.cond(
                            AiExpertState.current_response_display,
                            AiExpertState.current_response_display.content,
                            ""
                        ),
                        white_space="pre-wrap",
                        word_wrap="break-word",
                    ),
                    rx.cond(
                        AiExpertState.is_streaming,
                        rx.spinner(size="3"),
                    ),
                    align="center",
                    spacing="2",
                ),
                background_color="gray.100",
                color="black",
                padding="3",
                border_radius="lg",
                max_width="70%",
                align_self="flex-start",
            ),
            width="100%",
            display="flex",
            justify_content="flex-start",
            margin_bottom="3",
        ),
    )


def ai_expert_message_list() -> rx.Component:
    """List of chat messages with scrollable container."""
    return rx.auto_scroll(
        rx.vstack(
            rx.cond(
                AiExpertState.display_messages,
                rx.foreach(
                    AiExpertState.display_messages,
                    ai_expert_message_bubble,
                ),
                rx.text(
                    "Start asking questions about this document!",
                    color="gray.500",
                    font_size="sm",
                    text_align="center",
                    padding="4",
                ),
            ),
            ai_expert_current_message(),
            spacing="2",
            align="stretch",
        ),
        width="100%",
        border="1px solid",
        border_color="gray.200",
        border_radius="20px",
        padding='1em',
        flex="1"
    )
