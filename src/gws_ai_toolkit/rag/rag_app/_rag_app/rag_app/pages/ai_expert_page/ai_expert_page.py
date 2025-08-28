import reflex as rx
from gws_reflex_base import render_main_container

from gws_ai_toolkit.rag.rag_app._rag_app.rag_app.components.generic_chat.chat_config import \
    ChatConfig
from gws_ai_toolkit.rag.rag_app._rag_app.rag_app.components.generic_chat.generic_chat_interface import \
    generic_chat_interface

from ...components.shared.navigation import navigation
from .ai_expert_state import AiExpertState


def ai_expert_page() -> rx.Component:
    """AI Expert page component for document-specific chat."""
    config = ChatConfig(
        state=AiExpertState
    )

    return render_main_container(
        rx.vstack(
            navigation(),
            generic_chat_interface(config),
            spacing="0",
            min_height="100vh",
        )
    )
