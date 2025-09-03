from typing import List

import reflex as rx
from gws_reflex_base import render_main_container

from gws_ai_toolkit.rag.rag_app._rag_app.rag_app.components.generic_chat.chat_config import \
    ChatConfig
from gws_ai_toolkit.rag.rag_app._rag_app.rag_app.components.generic_chat.chat_state_base import \
    ChatStateBase
from gws_ai_toolkit.rag.rag_app._rag_app.rag_app.components.generic_chat.generic_chat_header import \
    header_clear_chat_button
from gws_ai_toolkit.rag.rag_app._rag_app.rag_app.components.generic_chat.generic_chat_interface import \
    generic_chat_interface

from ...components.shared.navigation import navigation
from .ai_expert_state import AiExpertState


def ai_expert_header_buttons(state: ChatStateBase) -> List[rx.Component]:
    """Header buttons for the AI Expert page."""
    return [
        # rx.button(
        #     rx.icon('file', size=16),
        #     "View document",
        #     on_click=lambda: AiExpertState.open_current_resource_doc,
        #     variant='outline',
        #     cursor="pointer",
        #     size="2",
        # ),
        header_clear_chat_button(state)
    ]


def ai_expert_page() -> rx.Component:
    """AI Expert page component for document-specific chat."""
    config = ChatConfig(
        state=AiExpertState,
        header_buttons=ai_expert_header_buttons
    )

    return render_main_container(
        rx.vstack(
            navigation(),
            generic_chat_interface(config),
            spacing="0",
            height="100vh",
        )
    )
