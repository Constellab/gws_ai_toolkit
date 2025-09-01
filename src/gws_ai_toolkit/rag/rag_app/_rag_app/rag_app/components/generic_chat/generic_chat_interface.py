import reflex as rx

from gws_ai_toolkit.rag.rag_app._rag_app.rag_app.pages.chat_page.chat_state import \
    ChatState

from .generic_chat_header import generic_chat_header
from .generic_chat_input import generic_chat_input
from .generic_message_list import generic_message_list


def _chat_with_messages(state: ChatState) -> rx.Component:
    """Chat interface with messages - fixed input at bottom"""
    return rx.box(
        rx.vstack(
            generic_chat_header(state),
            generic_message_list(state),
            width="100%",
            max_width="800px",
            margin="auto",
            padding="1em 1em 5em 1em",
            flex="1",
        ),
        # Fixed input at bottom
        rx.box(
            rx.box(
                generic_chat_input(state),
                background_color="white",
                border_radius="48px",
                padding="12px 28px 12px 24px",
                box_shadow="0 2px 8px rgba(0, 0, 0, 0.1)",
                max_width="90vw",
                width="100%",
                margin="auto",
            ),
            position="fixed",
            bottom="20px",
            left="50%",
            transform="translateX(-50%)",
            z_index="1000",
            padding="0 20px",
            width="800px",
        ),
        width="100%",
        position="relative",
        flex="1",
        display="flex",
        flex_direction="column",
    )


def _empty_chat(state: ChatState) -> rx.Component:
    """Chat interface when there are no messages"""
    return rx.vstack(
        generic_chat_header(state),
        rx.box(flex="1"),  # Spacer to push input to center
        rx.heading(
            state.empty_state_message,
            size="6",
            margin_bottom="1em",
            text_align="center",
            width="100%"
        ),
        rx.box(
            generic_chat_input(state),
            width="100%",
            max_width="800px",
            margin="auto",

            class_name="chat"
        ),
        rx.box(flex="2"),  # Spacer to center input
        width="100%",
        flex="1",
    )


def generic_chat_interface(state: ChatState) -> rx.Component:
    """Generic chat interface using chat page layout - only state is configurable"""

    # Use exact same layout as chat page
    return rx.auto_scroll(
        rx.box(
            rx.cond(
                # When there are messages, show normal layout with fixed input
                state.messages_to_display,
                # Layout with messages - fixed input at bottom
                _chat_with_messages(state),
                # When no messages, center the input vertically
                _empty_chat(state)
            ),
            width="100%",
            max_width="800px",
            margin="auto",
            padding="1em",
            flex="1",
            position="relative",
            display="flex",
            flex_direction="column"
        ),

        class_name='super-scroll-2',
        width="100%",
        flex="1",
        display="flex",
        flex_direction="column",
        min_height="0",
    )
