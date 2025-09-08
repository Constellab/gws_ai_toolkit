from dataclasses import dataclass
from typing import Callable, List, Type

import reflex as rx

from gws_ai_toolkit.rag.common.rag_models import RagChunk

from .chat_state_base import ChatStateBase


@dataclass
class ChatConfig:
    """Configuration class for chat components providing customization options.

    This dataclass defines the configuration parameters for chat components,
    allowing customization of state management, UI elements, and layout sections.
    It serves as the central configuration point for all chat interfaces in the
    application.

    The configuration supports:
        - Custom state management for different chat types
        - Configurable header buttons for chat-specific actions
        - Optional sources display component
        - Flexible left/right section layout

    Attributes:
        state (ChatStateBase): The state management class for the chat.
            Must extend ChatStateBase and provide chat functionality.

        header_buttons (Callable[[ChatStateBase], List[rx.Component]] | None):
            Optional function that returns custom header buttons. Takes the chat
            state as parameter and returns list of Reflex components.

        sources_component (Callable[[List[RagChunk], ChatStateBase], rx.Component] | None):
            Optional component function for displaying source references.
            Takes list of RAG chunks and chat state, returns display component.

        left_section (rx.Component | None): Optional component for left sidebar.

        right_section (rx.Component | None): Optional component for right sidebar.

    Example:
        config = ChatConfig(
            state=MyCustomChatState,
            header_buttons=lambda state: [custom_button],
            sources_component=sources_display_component,
            left_section=sidebar_component
        )
    """

    # State configuration - this is the only customizable part
    state: Type[ChatStateBase]

    # Add custom button on top right of the header
    header_buttons: Callable[[ChatStateBase], List[rx.Component]] | None = None

    sources_component: Callable[[List[RagChunk], ChatStateBase], rx.Component] | None = None

    # Optional left and right sections to display alongside the chat
    left_section: Callable[[ChatStateBase], rx.Component] | None = None

    right_section: Callable[[ChatStateBase], rx.Component] | None = None
