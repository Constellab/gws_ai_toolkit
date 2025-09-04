import reflex as rx

from .chat_config import ChatConfig
from .chat_message_class import (ChatMessage, ChatMessageCode,
                                 ChatMessageImage, ChatMessageText)
from .chat_state_base import ChatStateBase


def _message_bubble(message: ChatMessage, config: ChatConfig) -> rx.Component:
    """Generic message bubble - uses chat page styling with support for different message types"""

    return rx.cond(
        message.role == "user",
        # User message - right aligned with darker background (exact same as chat page)
        rx.box(
            rx.box(
                _message_content(message),
                background_color="var(--accent-10)",
                padding="0px 16px",
                border_radius="18px",
                max_width="70%",
                word_wrap="break-word",
                color="white",
            ),
            display="flex",
            justify_content="flex-end",
            margin="8px 0",
            width="100%",
        ),
        # Assistant message - left aligned without background (exact same as chat page)
        rx.box(
            rx.box(
                _message_content(message),
                rx.cond(
                    message.sources,
                    rx.box(
                        config.sources_component(message.sources, config.state) if config.sources_component else None
                    )
                ),
                padding="12px 0",
                word_wrap="break-word",
                width="100%",
            ),
            display="flex",
            justify_content="flex-start",
            margin="8px 0",
            width="100%",
        )
    )


def _streaming_indicator(state_class: ChatStateBase) -> rx.Component:
    """Generic streaming indicator - same as chat page"""
    return rx.cond(
        state_class.is_streaming,
        rx.box(
            rx.hstack(
                rx.spinner(),
                rx.text("Assistant is thinking...", font_style="italic", color="gray.600"),
                spacing="2",
            ),
            margin="0.5em 0",
            width="100%",
            align_items="center"
        ),
        rx.text("")
    )


def chat_messages_list_component(config: ChatConfig) -> rx.Component:
    """Generic message list - uses chat page layout"""

    return rx.box(
        rx.foreach(
            config.state.messages_to_display,
            lambda message: _message_bubble(message, config)
        ),
        # Display current response message separately
        rx.cond(
            config.state.current_response_message,
            _message_bubble(config.state.current_response_message, config),
            rx.text("")
        ),
        _streaming_indicator(config.state),
        width="100%",
        padding='1em',
        flex="1",
    )


def _message_content(message: ChatMessage) -> rx.Component:
    """Render message content based on message type"""

    return rx.match(
        message.type,
        ("text", _text_content(message)),
        ("image", _image_content(message)),
        ("code", _code_content(message)),
        rx.text(f"Unsupported message type {message.type}.")
    )


def _text_content(message: ChatMessageText) -> rx.Component:
    """Render text message content"""
    return rx.markdown(
        message.content,
        font_size="14px",
    )


def _image_content(message: ChatMessageImage) -> rx.Component:
    """Render image message content"""
    return rx.vstack(
        rx.cond(
            message.content,  # If there's text content along with the image
            rx.markdown(
                message.content,
                font_size="14px",
            ),
            rx.text("")
        ),
        rx.image(
            src=message.data,  # Now data is available on the base class
            max_width="100%",
            height="auto",
            border_radius="8px",
            margin="0.5em 0",
        ),
        spacing="2"
    )


def _code_content(message: ChatMessageCode) -> rx.Component:
    """Render code message content"""
    return rx.code_block(
        message.content,
        language="python",
        border_radius="8px",
        padding="1em",
    )
