import reflex as rx

from .chat_config import ChatConfig
from .generic_chat_class import ChatMessage
from .generic_sources_list import sources_list


def generic_message_bubble(message: ChatMessage) -> rx.Component:
    """Generic message bubble - uses chat page styling"""
    return rx.cond(
        message.role == "user",
        # User message - right aligned with darker background (exact same as chat page)
        rx.box(
            rx.box(
                rx.markdown(
                    message.content,
                    color="white",
                    font_size="14px",
                    class_name='waow'
                ),
                background_color="#374151",
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
                rx.markdown(
                    message.content,
                ),
                rx.cond(
                    message.sources,
                    sources_list(message.sources)
                ),
                padding="12px 0",
                word_wrap="break-word",
            ),
            display="flex",
            justify_content="flex-start",
            margin="8px 0",
            width="100%",
        )
    )


def generic_streaming_indicator(state_class) -> rx.Component:
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


def generic_message_list(config: ChatConfig) -> rx.Component:
    """Generic message list - uses chat page layout"""

    return rx.auto_scroll(
        rx.foreach(
            config.state.chat_messages,
            generic_message_bubble
        ),
        # Display current response message separately
        rx.cond(
            config.state.current_response_message,
            generic_message_bubble(config.state.current_response_message),
            rx.text("")
        ),
        generic_streaming_indicator(config.state),
        width="100%",
        padding='1em',
        flex="1",
        class_name='super-scroll'
    )
