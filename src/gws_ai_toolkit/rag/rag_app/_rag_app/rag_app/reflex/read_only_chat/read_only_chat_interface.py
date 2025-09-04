import reflex as rx

from ..chat_base.chat_config import ChatConfig
from ..chat_base.chat_header_component import chat_header_component
from ..chat_base.messages_list_component import chat_messages_list_component


def _read_only_chat_with_messages(config: ChatConfig) -> rx.Component:
    """Read-only chat interface with messages - fixed input at bottom (disabled)"""
    return rx.box(
        rx.vstack(
            chat_header_component(config),
            chat_messages_list_component(config),
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
        chat_header_component(config),
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


def read_only_chat_component(config: ChatConfig) -> rx.Component:
    """Read-only generic chat interface - input is disabled"""

    # Use exact same layout as chat page but with disabled input
    return rx.box(
        rx.cond(
            # When there are messages, show normal layout with disabled input
            config.state.messages_to_display,
            # Layout with messages - disabled input at bottom
            _read_only_chat_with_messages(config),
            # When no messages, center the disabled input vertically
            _read_only_empty_chat(config)
        ),
        width="100%",
        flex="1",
        display="flex",
        flex_direction="column",
        min_height="0",
        overflow_y="auto",
    )
