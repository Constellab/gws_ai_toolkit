from collections.abc import Callable

import reflex as rx

from ..chat_base.chat_component import chat_component
from ..chat_base.chat_config import ChatConfig, ChatMessageRenderer
from ..chat_base.conversation_chat_state_base import ConversationChatStateBase
from .rag_chat_config_state import RagChatConfigState
from .rag_chat_state import RagChatState
from .rag_empty_chat_component import rag_empty_chat_component
from .rag_page_layout_component import rag_header_component


def rag_chat_config_factory(
    left_section: Callable[[ConversationChatStateBase], rx.Component] | None = None,
    right_section: Callable[[ConversationChatStateBase], rx.Component] | None = None,
    custom_chat_messages: dict[str, ChatMessageRenderer] | None = None,
) -> ChatConfig:
    """Factory function to create a ChatConfig for the RAG Chat page.

    This allows the header and empty chat component to be configured consistently
    across all apps that use the RAG chat.

    Args:
        left_section: Optional left section component builder.
        right_section: Optional right section component builder.
        custom_chat_messages: Optional custom chat message renderers by type.

    Returns:
        ChatConfig: The configuration for the RAG chat component.
    """
    _header = rag_header_component(
        RagChatState.subtitle,
        show_settings=RagChatConfigState.show_settings_menu,
    )

    return ChatConfig(
        state=RagChatState,
        header=_header,
        left_section=left_section,
        right_section=right_section,
        custom_chat_messages=custom_chat_messages,
    )


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
            If None, creates a default configuration using rag_chat_config_factory.
            The ChatConfig allows customization of the state class and UI components used.

    Returns:
        rx.Component: The complete RAG Chat component including message list, input field,
            and source references panel.

    Example:
        # Use with default configuration
        component = rag_chat_component()

        # Use with custom configuration
        custom_config = rag_chat_config_factory(
            custom_chat_messages={"source": my_source_renderer}
        )
        component = rag_chat_component(custom_config)
    """

    if not chat_config:
        chat_config = rag_chat_config_factory()

    return chat_component(chat_config, empty_chat_component=rag_empty_chat_component)
