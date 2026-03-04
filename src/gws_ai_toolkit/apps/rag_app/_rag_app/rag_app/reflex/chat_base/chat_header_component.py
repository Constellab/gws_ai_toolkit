from collections.abc import Callable

import reflex as rx

from .chat_config import ChatConfig


def header_clear_chat_button_component(clear_chat: Callable[[], None], text: str) -> rx.Component:
    """Standard clear chat button component for chat headers.

    Provides a consistent clear chat button that can be used in any chat header.
    The button displays a refresh icon with configurable text and triggers the
    chat clearing functionality from the provided state.

    Args:
        clear_chat (Callable[[], None]): Function to clear the chat.
        text (str): Text to display on the button.

    Returns:
        rx.Component: Button component with refresh icon and clear functionality.

    Example:
        clear_btn = header_clear_chat_button_component(lambda: chat_state.clear_chat(), "Clear Chat")
        # Creates button with refresh icon and "Clear Chat" text
    """
    return rx.button(
        rx.icon("plus", size=16),
        text,
        on_click=clear_chat,
        variant="outline",
        size="2",
    )
