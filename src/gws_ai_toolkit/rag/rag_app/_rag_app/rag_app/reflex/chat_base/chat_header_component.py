from typing import List

import reflex as rx

from .chat_config import ChatConfig
from .chat_state_base import ChatStateBase


def header_clear_chat_button_component(state: ChatStateBase) -> rx.Component:
    """Standard clear chat button component for chat headers.

    Provides a consistent clear chat button that can be used in any chat header.
    The button displays a refresh icon with configurable text and triggers the
    chat clearing functionality from the provided state.

    Args:
        state (ChatStateBase): Chat state instance providing clear_chat method
            and clear_button_text property.

    Returns:
        rx.Component: Button component with refresh icon and clear functionality.

    Example:
        clear_btn = header_clear_chat_button_component(chat_state)
        # Creates button with refresh icon and "Clear Chat" text
    """
    return rx.button(
        rx.icon("refresh-cw", size=16),
        state.clear_button_text,
        on_click=state.clear_chat,
        variant="outline",
        size="2",
    )


def chat_header_component(config: ChatConfig) -> rx.Component:
    """Universal chat header component with title, subtitle, and action buttons.

    This component provides a consistent header layout for all chat interfaces,
    displaying the chat title, optional subtitle, and configurable action buttons.
    It automatically handles button configuration and provides a professional
    appearance across different chat types.

    Features:
        - Dynamic title and subtitle display
        - Configurable action buttons (defaults to clear chat button)
        - Consistent spacing and alignment
        - Responsive layout that adapts to content
        - Integration with chat state for dynamic content

    Args:
        config (ChatConfig): Chat configuration containing:
            - state: Provides title, subtitle, and state methods
            - header_buttons: Optional custom buttons function

    Returns:
        rx.Component: Complete header with title, subtitle, and action buttons
            arranged in a horizontal layout with proper spacing.

    Example:
        header = chat_header_component(chat_config)
        # Displays title, subtitle (if present), and configured buttons
    """

    header_buttons: List[rx.Component] = []
    if config.header_buttons is None:
        # default value
        header_buttons = [header_clear_chat_button_component(config.state)]
    else:
        header_buttons = config.header_buttons(config.state)

    return rx.vstack(

        rx.hstack(
            rx.vstack(
                rx.heading(config.state.title, size="6"),
                rx.cond(
                    config.state.subtitle,
                    rx.text(config.state.subtitle, size="2"),
                ),
                spacing="0"
            ),
            rx.spacer(),
            *header_buttons,
            width="100%",
            align="center",
        ),
        width="100%"
    )
