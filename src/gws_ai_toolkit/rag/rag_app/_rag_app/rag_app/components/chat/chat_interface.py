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
                border_radius="24px",
                style={'input': {'padding-inline': '12px'}},
                size="3"
            ),
            rx.button(
                rx.icon("send", size=18),
                type="submit",
                disabled=ChatState.is_streaming,
                cursor="pointer",
                variant="ghost",
                padding="8px",
                size="3",
                border_radius="50%"
            ),
            width="100%",
            spacing="5",
            align_items="center"
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
    return rx.cond(
        # When there are messages, show normal layout with fixed input
        ChatState.display_messages,
        # Layout with messages - fixed input at bottom
        rx.box(
            rx.vstack(
                chat_header(),
                message_list(),
                width="100%",
                max_width="800px",
                margin="auto",
                flex="1",
                padding_top="1em",
                padding_bottom="100px",  # Space for fixed input
            ),
            # Fixed input at bottom
            rx.box(
                rx.box(
                    chat_input(),
                    background_color="white",
                    border_radius="48px",
                    padding="12px 28px 12px 24px",
                    box_shadow="0 2px 8px rgba(0, 0, 0, 0.1)",
                    max_width="90vw",
                    width="700px",
                    margin="auto",
                ),
                position="fixed",
                bottom="20px",
                left="50%",
                transform="translateX(-50%)",
                z_index="1000",
                padding="0 20px",
            ),
            width="100%",
            min_height="100vh",
            position="relative",
        ),
        # When no messages, center the input vertically
        rx.box(
            rx.vstack(
                chat_header(),
                rx.box(flex="1"),  # Spacer to push input to center
                rx.heading("Start talking to the AI",
                           size="6",
                           margin_bottom="1em",
                           text_align="center",
                           width="100%"
                           ),
                rx.box(
                    chat_input(),
                    width="100%",
                    max_width="800px",
                    margin="auto",
                ),
                rx.box(flex="2"),  # Spacer to center input
                width="100%",
                height="100vh",
                max_width="800px",
                margin="auto",
                padding="1em",
            ),
            width="100%",
            min_height="100vh",
        )
    )
