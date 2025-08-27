import reflex as rx
from gws_reflex_base import render_main_container

from ..components.ai_expert.ai_expert_interface import ai_expert_chat_interface
from ..components.shared.navigation import navigation


def ai_expert_page() -> rx.Component:
    """AI Expert page component for document-specific chat."""
    return render_main_container(
        rx.vstack(
            navigation(),
            ai_expert_chat_interface(),
            spacing="0",
            min_height="100vh",
        )
    )