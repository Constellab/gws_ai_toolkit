import reflex as rx

from .chat_config import ChatConfig
from .generic_chat_header import generic_chat_header
from .generic_message_list import generic_message_list


def _read_only_chat_with_messages(config: ChatConfig) -> rx.Component:
    """Read-only chat interface with messages - fixed input at bottom (disabled)"""
    return rx.box(
        rx.vstack(
            generic_chat_header(config),
            generic_message_list(config),
            width="100%",
            max_width="800px",
            margin="auto",
            padding="1em 1em 5em 1em",
            flex="1",
        ),
        width="100%",
        flex="1",
        display="flex",
        flex_direction="column",
    )


def _read_only_empty_chat(config: ChatConfig) -> rx.Component:
    """Read-only chat interface when there are no messages"""
    return rx.vstack(
        generic_chat_header(config),
        rx.box(flex="1"),  # Spacer to push content to center
        rx.heading(
            config.state.empty_state_message,
            size="6",
            margin_bottom="1em",
            text_align="center",
            width="100%"
        ),
        rx.box(flex="2"),  # Spacer to center content
        width="100%",
        flex="1",
    )


def read_only_chat_interface(config: ChatConfig) -> rx.Component:
    """Read-only generic chat interface - input is disabled"""

    # Use exact same layout as chat page but with disabled input
    return rx.auto_scroll(
        rx.box(
            rx.cond(
                # When there are messages, show normal layout with disabled input
                config.state.messages_to_display,
                # Layout with messages - disabled input at bottom
                _read_only_chat_with_messages(config),
                # When no messages, center the disabled input vertically
                _read_only_empty_chat(config)
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
