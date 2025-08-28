import reflex as rx
from gws_ai_toolkit.rag.rag_app._rag_app.rag_app.components.generic_chat.chat_config import \
    ChatConfig
from gws_ai_toolkit.rag.rag_app._rag_app.rag_app.components.generic_chat.generic_chat_interface import \
    generic_chat_interface
from gws_ai_toolkit.rag.rag_app._rag_app.rag_app.components.generic_chat.generic_sources_list import \
    generic_sources_list
from gws_reflex_base import render_main_container

from ...components.shared.navigation import navigation
from .chat_state import ChatState


def chat_page() -> rx.Component:
    """Chat page component."""
    config = ChatConfig(
        state=ChatState,
        sources_component=generic_sources_list
    )

    return render_main_container(
        rx.vstack(
            navigation(),
            generic_chat_interface(config),
            spacing="0",
            height="100vh",
        )
    )
