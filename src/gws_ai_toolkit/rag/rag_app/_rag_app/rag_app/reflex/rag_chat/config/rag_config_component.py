import reflex as rx

from .rag_config_file_bulk import rag_config_file_bulk
from .sync_resource.sync_resource_component import search_resource


def rag_config_component() -> rx.Component:
    """Resource management page component."""
    return rx.vstack(
        rx.heading("Resource Management", size="8", mb="4"),
        rag_config_file_bulk(),
        rx.divider(),
        search_resource(),
        spacing="6",
        padding="1em",
    )
