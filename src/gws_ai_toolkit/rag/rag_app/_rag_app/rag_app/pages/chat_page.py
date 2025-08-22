import reflex as rx
from gws_reflex_base import render_main_container

from ..components.chat.chat_interface import chat_interface
from ..components.shared.navigation import navigation


def chat_page() -> rx.Component:
    """Chat page component."""
    return render_main_container(
        rx.vstack(
            navigation(),
            chat_interface(),
            spacing="0",
            min_height="100vh",
        )
    )
