from typing import List

import reflex as rx
from gws_ai_toolkit.rag.rag_app._rag_app.rag_app.components.generic_chat.chat_config import \
    ChatConfig
from gws_ai_toolkit.rag.rag_app._rag_app.rag_app.components.generic_chat.generic_chat_interface import \
    generic_chat_interface
from gws_reflex_base import render_main_container

from ...components.shared.navigation import navigation
from .ai_expert_state import AiExpertState


def ai_expert_header_buttons() -> List[rx.Component]:
    """Header buttons for the AI Expert page."""
    return [
        rx.button("View document", on_click=lambda: AiExpertState.open_current_resource_doc,
                  variant='outline', cursor="pointer"),
    ]


def breadcrumb_menu() -> rx.Component:
    return rx.hstack(
        rx.link(rx.text("AI Chat"), cursor="pointer", href="/"),
        rx.text(" / "),
        rx.text("AI Expert"),
        rx.text(" / "),
        rx.text(AiExpertState.document_name),
        align="center",
        align_items="center",
        margin_inline="auto",
        margin_top="5px"
    )


def ai_expert_page() -> rx.Component:
    """AI Expert page component for document-specific chat."""
    config = ChatConfig(
        state=AiExpertState,
        header_buttons=ai_expert_header_buttons
    )

    return render_main_container(
        rx.vstack(
            navigation(),
            # breadcrumb_menu(),
            generic_chat_interface(config),
            spacing="0",
            height="100vh",
        )
    )
