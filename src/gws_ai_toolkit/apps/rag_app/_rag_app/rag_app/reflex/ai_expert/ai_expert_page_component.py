from collections.abc import Callable

import reflex as rx
from gws_ai_toolkit.models.chat.message.chat_message_base import ChatMessageBase

from ..chat_base.chat_config import ChatConfig
from ..chat_base.conversation_chat_state_base import ConversationChatStateBase
from ..rag_chat.rag_page_layout_component import rag_page_layout_component
from .ai_expert_component import ai_expert_component
from .ai_expert_config_state import AiExpertConfigState
from .ai_expert_header_component import ai_expert_header_component
from .ai_expert_state import AiExpertState


def ai_expert_chat_config_factory(
    left_section: Callable[[ConversationChatStateBase], rx.Component] | None = None,
    right_section: Callable[[ConversationChatStateBase], rx.Component] | None = None,
    custom_chat_messages: dict[str, Callable[[ChatMessageBase], rx.Component]] | None = None,
) -> ChatConfig:
    """Factory function to create a ChatConfig for the AI Expert page.

    This allows the header to be dynamically updated based on the AiExpertState.

    Returns:
        ChatConfig: The configuration for the AI Expert chat component.
    """
    _header = ai_expert_header_component(
        AiExpertState.subtitle,
        AiExpertState.open_current_resource_file,
        show_settings=AiExpertConfigState.show_settings_menu,
    )

    return ChatConfig(
        state=AiExpertState,
        header=_header,
        left_section=left_section,
        right_section=right_section,
        custom_chat_messages=custom_chat_messages,
    )


def ai_expert_page_content(config: ChatConfig | None = None) -> rx.Component:
    """Build the AI Expert page content with header and expert component.

    Creates a ChatConfig with the AI Expert header (showing subtitle and
    resource file link) and wraps it in the RAG page layout.

    Returns:
        rx.Component: The AI Expert page wrapped in rag_page_layout_component.
    """

    if config is None:
        config = ai_expert_chat_config_factory()

    return rag_page_layout_component(
        content=ai_expert_component(config),
    )
