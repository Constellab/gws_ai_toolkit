import reflex as rx

from .rag_config_file_bulk import rag_config_file_bulk
from .sync_resource.sync_resource_component import search_resource


def rag_config_component() -> rx.Component:
    """Complete resource management interface component.

    This component provides a comprehensive interface for managing RAG resources,
    including bulk operations, resource synchronization, and search functionality.
    It combines multiple sub-components to offer complete resource management
    capabilities.

    Features:
        - Bulk resource management operations
        - Resource search and filtering
        - Synchronization controls
        - Professional layout with proper spacing

    Returns:
        rx.Component: Complete resource management interface with all tools
            and controls needed for RAG resource administration.

    Example:
        resource_ui = rag_config_component()
        # Renders complete resource management page
    """
    return rx.vstack(
        rx.heading("Resource Management", size="8", mb="4"),
        rag_config_file_bulk(),
        rx.divider(),
        search_resource(),
        spacing="6",
        padding="1em",
    )
