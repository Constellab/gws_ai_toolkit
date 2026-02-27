import reflex as rx

from ..chat_base.chat_component import chat_component
from ..chat_base.chat_config import ChatConfig
from .ai_expert_state import AiExpertState


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

    The component uses AiExpertState for state management, which handles:
        - Document loading and processing
        - AI model communication with document context
        - Configuration management for processing modes
        - Resource management and document metadata

    Args:
        chat_config (ChatConfig | None, optional): Custom ChatConfig to override the defaults.
            If None, creates a default configuration with AiExpertState.
            Allows customization of state class and UI components.

    Returns:
        rx.Component: Complete AI Expert chat interface with document-specific features,
            message display, and input functionality.

    Example:
        # Use with default configuration
        component = ai_expert_component()

        # Use with custom configuration
        custom_config = ChatConfig(state=AiExpertState)
        component = ai_expert_component(custom_config)
    """
    if not chat_config:
        chat_config = ChatConfig(state=AiExpertState)

    return chat_component(chat_config)
