import reflex as rx
from gws_reflex_base import render_main_container

from gws_ai_toolkit.rag.rag_app._rag_app.rag_app.components.generic_chat.chat_config import \
    ChatConfig
from gws_ai_toolkit.rag.rag_app._rag_app.rag_app.components.generic_chat.generic_chat_interface import \
    generic_chat_interface
from gws_ai_toolkit.rag.rag_app._rag_app.rag_app.components.generic_chat.generic_sources_list import \
    generic_sources_list
from gws_ai_toolkit.rag.rag_app._rag_app.rag_app.states.main_state import \
    RagAppState

from ...components.shared.navigation import navigation
from .chat_state import ChatState
from .edit_test import MainState, reusable_counter


def chat_page() -> rx.Component:
    """Chat page component."""
    config = ChatConfig(
        state=ChatState,
        sources_component=generic_sources_list
    )

    component_ = ChatState.build_component(
        chat_rag_app_service=RagAppState.get_chat_rag_app_service,
        chat_id=RagAppState.get_chat_id,
        sources_component=generic_sources_list
    )

    element = reusable_counter(initial_value=MainState.initial_value)
    return render_main_container(
        rx.vstack(
            navigation(),
            element,
            # element.State.bonjour,
            component_,
            spacing="0",
            height="100vh",
        )
    )
