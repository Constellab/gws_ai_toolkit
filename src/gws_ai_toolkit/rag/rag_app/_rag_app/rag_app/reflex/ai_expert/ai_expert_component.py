from typing import List

import reflex as rx

from ...reflex.ai_expert.ai_expert_state import AiExpertState
from ..chat_base.chat_component import chat_component
from ..chat_base.chat_config import ChatConfig
from ..chat_base.chat_header_component import \
    header_clear_chat_button_component
from ..chat_base.chat_state_base import ChatStateBase


def ai_expert_header_default_buttons_component(state: ChatStateBase) -> List[rx.Component]:
    """Default header buttons for the AI Expert chat interface.

    Provides standard action buttons for the AI Expert page including document viewing
    and chat clearing functionality. These buttons are displayed in the chat header
    and provide quick access to common actions.

    Features:
        - View document button: Opens the current document being analyzed
        - Clear chat button: Clears the current conversation history

    Args:
        state (ChatStateBase): The current chat state instance for accessing state methods

    Returns:
        List[rx.Component]: List of Reflex button components ready for header display

    Example:
        buttons = ai_expert_header_default_buttons_component(ai_expert_state)
        # Returns: [view_document_button, clear_chat_button]
    """
    return [
        rx.button(
            rx.icon('file', size=16),
            "View document",
            on_click=lambda: AiExpertState.open_current_resource_doc,
            variant='outline',
            cursor="pointer",
            size="2",
        ),
        header_clear_chat_button_component(state)
    ]


def ai_expert_component(chat_config: ChatConfig | None = None) -> rx.Component:
    """AI Expert chat component for document-specific intelligent conversations.

    This component provides a specialized chat interface for having detailed conversations
    about a specific document. Unlike general RAG chat, the AI Expert focuses on a single
    document and provides in-depth analysis, explanations, and answers based on the
    complete document context.

    Features:
        - Document-focused AI conversations with full context awareness
        - Multiple processing modes (full text, relevant chunks, or full file upload)
        - Configurable AI models and parameters
        - Document viewing and navigation capabilities
        - Persistent conversation history for the specific document
        - Custom header buttons for document-specific actions

    The component uses AiExpertState for state management, which handles:
        - Document loading and processing
        - AI model communication with document context
        - Configuration management for processing modes
        - Resource management and document metadata

    Args:
        chat_config (ChatConfig | None, optional): Custom ChatConfig to override the defaults.
            If None, creates a default configuration with AiExpertState and default header buttons.
            Allows customization of state class and UI components.

    Returns:
        rx.Component: Complete AI Expert chat interface with document-specific features,
            header buttons, message display, and input functionality.

    Example:
        # Use with default configuration
        component = ai_expert_component()

        # Use with custom configuration
        custom_config = ChatConfig(
            state=AiExpertState,
            header_buttons=custom_header_buttons
        )
        component = ai_expert_component(custom_config)
    """
    if not chat_config:
        chat_config = ChatConfig(
            state=AiExpertState,
            header_buttons=ai_expert_header_default_buttons_component
        )

    return chat_component(chat_config)
