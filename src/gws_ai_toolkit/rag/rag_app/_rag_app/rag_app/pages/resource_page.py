import reflex as rx
from gws_reflex_base import render_main_container

from gws_ai_toolkit.rag.rag_app._rag_app.rag_app.reflex.rag_chat.config.rag_config_file_bulk import \
    rag_config_file_bulk
from gws_ai_toolkit.rag.rag_app._rag_app.rag_app.reflex.rag_chat.config.sync_resource.sync_resource_component import \
    search_resource

from ..components.shared.navigation import navigation


def resource_page() -> rx.Component:
    """Resource management page component."""
    return render_main_container(
        rx.vstack(
            navigation(),
            rx.container(
                rx.vstack(
                    rx.heading("Resource Management", size="8", mb="4"),
                    rag_config_file_bulk(),
                    rx.divider(),
                    search_resource(),
                    spacing="6",
                    align="start",
                ),
                max_width="1200px",
                p="4",
            ),
            spacing="0",
            min_height="100vh",
        )
    )
