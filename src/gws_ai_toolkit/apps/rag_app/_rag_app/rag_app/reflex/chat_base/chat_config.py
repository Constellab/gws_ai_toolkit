from collections.abc import Callable
from dataclasses import dataclass

import reflex as rx
from gws_ai_toolkit.models.chat.message.chat_message_base import ChatMessageBase

from .conversation_chat_state_base import ConversationChatStateBase


@dataclass
class ChatConfig:
    """Configuration class for chat components providing customization options.

    This dataclass defines the configuration parameters for chat components,
    allowing customization of state management, UI elements, and layout sections.
    It serves as the central configuration point for all chat interfaces in the
    application.

    The configuration supports:
        - Custom state management for different chat types
        - Optional sources display component
        - Flexible left/right section layout

    Attributes:
        state (ConversationChatStateBase): The state management class for the chat.
            Must extend ConversationChatStateBase and provide chat functionality.

        sources_component (SourcesComponentBuilder | None):
            Optional component function for displaying source references.
            Takes list of RAG chunks and chat state, returns display component.

        left_section (rx.Component | None): Optional component for left sidebar.

        right_section (rx.Component | None): Optional component for right sidebar.

    Example:
        config = ChatConfig(
            state=MyCustomChatState,
            sources_component=sources_display_component,
            left_section=sidebar_component
        )
    """

    # State configuration - this is the only customizable part
    state: type[ConversationChatStateBase]

    # Optional header component rendered at the top of the chat area.
    header: rx.Component | None = None

    # Optional left and right sections to display alongside the chat
    left_section: Callable[[ConversationChatStateBase], rx.Component] | None = None

    right_section: Callable[[ConversationChatStateBase], rx.Component] | None = None

    custom_chat_messages: dict[str, Callable[[ChatMessageBase], rx.Component]] | None = None

    # Optional custom component to display when the chat is empty (no messages).
    # Takes the ChatConfig as parameter and returns a Reflex component.
    # When not provided, the default empty chat layout is used.
    empty_chat_component: Callable[["ChatConfig"], rx.Component] | None = None
