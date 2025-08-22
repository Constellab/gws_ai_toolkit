
import reflex as rx

from ...states.chat_state import ChatMessage, ChatState
from .sources_display import sources_display


def message_bubble(message: ChatMessage) -> rx.Component:
    """Create a message bubble component."""
    return rx.box(
        rx.text(
            rx.cond(
                message.role == "user",
                "You: ",
                "Assistant: "
            ),
            font_weight="bold",
            margin_bottom="0.5em",
        ),
        rx.markdown(
            message.content,
        ),
        rx.cond(
            message.sources,
            sources_display(message.sources)
        ),
        margin="0.5em 0",
        width="100%",
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
        border="1px solid",
        border_color="gray.200",
        border_radius="20px",
        padding='1em',
        flex="1"
    )
