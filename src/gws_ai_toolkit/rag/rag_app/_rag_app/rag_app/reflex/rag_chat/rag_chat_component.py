import reflex as rx

from ...reflex.rag_chat.rag_chat_state import RagChatState
from ..chat_base.chat_component import chat_component
from ..chat_base.chat_config import ChatConfig
from ..chat_base.sources_list_component import sources_list_component


def rag_chat_component(chat_config: ChatConfig | None = None) -> rx.Component:
    """RAG Chat component for document-specific chat.
    It uses the RagChatState for state management.

    Args:
        chat_config (ChatConfig | None, optional): Custom ChatConfig to override the defaults. Defaults to None.

    Returns:
        rx.Component: The RAG Chat component.
    """

    if not chat_config:
        chat_config = ChatConfig(
            state=RagChatState,
            sources_component=sources_list_component
        )

    return chat_component(chat_config)
