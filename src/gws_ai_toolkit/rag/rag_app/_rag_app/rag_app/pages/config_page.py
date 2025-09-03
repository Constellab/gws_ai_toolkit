import reflex as rx
from gws_reflex_base import render_main_container

from gws_ai_toolkit.rag.rag_app._rag_app.rag_app.reflex.ai_expert.ai_expert_config_component import \
    show_ai_expert_config_section

from ..components.shared.navigation import navigation


def config_page() -> rx.Component:
    """Configuration page component."""
    return render_main_container(
        rx.vstack(
            navigation(),
            rx.container(
                rx.vstack(
                    rx.heading("Configuration", size="8", mb="4"),
                    show_ai_expert_config_section(),
                    spacing="6",
                    align="start",
                ),
                width="100%",
            ),
            spacing="0",
            min_height="100vh",
            width="100%"
        )
    )
