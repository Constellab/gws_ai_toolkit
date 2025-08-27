
import reflex as rx

from ...states.chat_state import ChatMessage, ChatState
from .sources_display import sources_display


def message_bubble(message: ChatMessage) -> rx.Component:
    """Create a message bubble component styled like ChatGPT."""
    return rx.cond(
        message.role == "user",
        # User message - right aligned with darker background
        rx.box(
            rx.box(
                rx.markdown(
                    message.content,
                    color="white",
                    font_size="14px",
                    class_name='waow'
                ),
                background_color="#374151",  # Darker gray for better contrast
                padding="0px 16px",
                border_radius="18px",
                max_width="70%",
                word_wrap="break-word",
                color="white",  # Ensure text color inheritance
            ),
            display="flex",
            justify_content="flex-end",
            margin="8px 0",
            width="100%",
        ),
        # Assistant message - left aligned without background
        rx.box(
            rx.box(
                rx.markdown(
                    message.content,
                ),
                rx.cond(
                    message.sources,
                    sources_display(message.sources)
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


def streaming_indicator() -> rx.Component:
    """Show loading indicator when streaming."""
    return rx.cond(
        ChatState.is_streaming,
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


def message_list() -> rx.Component:
    """Component to display the list of chat messages."""
    return rx.auto_scroll(
        rx.foreach(
            ChatState.display_messages,
            message_bubble
        ),
        # Display current response message separately
        rx.cond(
            ChatState.current_response_display,
            message_bubble(ChatState.current_response_display),
            rx.text("")
        ),
        streaming_indicator(),
        width="100%",
        padding='1em',
        flex="1"
    )
