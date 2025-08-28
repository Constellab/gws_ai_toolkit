import reflex as rx
from gws_reflex_base import render_main_container

from gws_ai_toolkit.rag.rag_app._rag_app.rag_app.components.generic_chat.chat_config import \
    ChatConfig
from gws_ai_toolkit.rag.rag_app._rag_app.rag_app.components.generic_chat.generic_chat_interface import \
    generic_chat_interface

from ...components.shared.navigation import navigation
from .chat_state import ChatState


def chat_page() -> rx.Component:
    """Chat page component."""
    config = ChatConfig(
        state=ChatState
    )

    return render_main_container(
        rx.vstack(
            navigation(),
            generic_chat_interface(config),
            spacing="0",
            height="100vh",
        )
    )
