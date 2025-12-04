import reflex as rx

from ..chat_base.chat_component import chat_component
from ..chat_base.chat_config import ChatConfig
from ..chat_base.messages_list_component import message_source
from ..chat_base.sources_list_component import sources_list_component
from .rag_chat_state import RagChatState


def rag_chat_component(chat_config: ChatConfig | None = None) -> rx.Component:
    """RAG Chat component for Retrieval Augmented Generation conversations.

    This component provides a complete chat interface that integrates with RAG services
    to enable conversations with knowledge from indexed documents. It supports streaming
    responses, source citations, and real-time interaction with the configured RAG provider
    (Dify or RagFlow).

    Features:
        - Real-time streaming chat with RAG-enhanced responses
        - Source document citations and references
        - Message history persistence
        - Configurable RAG provider integration
        - Responsive UI with message list and input components

    The component uses RagChatState for state management, which handles:
        - Communication with RAG services
        - Message streaming and display
        - Source document retrieval and display
        - Configuration management

    Args:
        chat_config (ChatConfig | None, optional): Custom ChatConfig to override the defaults.
            If None, creates a default configuration with RagChatState and sources_list_component.
            The ChatConfig allows customization of the state class and UI components used.

    Returns:
        rx.Component: The complete RAG Chat component including message list, input field,
            and source references panel.

    Example:
        # Use with default configuration
        component = rag_chat_component()

        # Use with custom configuration
        custom_config = ChatConfig(
            state=RagChatState,
            sources_component=custom_sources_component
        )
        component = rag_chat_component(custom_config)
    """

    if not chat_config:
        chat_config = ChatConfig(
            state=RagChatState,
            custom_chat_messages={
                "source": lambda message: message_source(
                    message, RagChatState, sources_list_component
                ),
            },
        )

    return chat_component(chat_config)
