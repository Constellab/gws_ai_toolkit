from typing import Optional

import reflex as rx

from .main_state import RagAppState


class ConfigState(RagAppState):
    """State management for the configuration functionality."""

    # Resource selection and management
    selected_resource_id: Optional[str] = None
    selected_resource_name: str = ""
    selected_resource_synced: bool = False

    @rx.var
    def get_selected_resource_info(self) -> str:
        """Get info about the currently selected resource."""
        if self.selected_resource_id:
            status = "synced" if self.selected_resource_synced else "not synced"
            return f"{self.selected_resource_name} - {status}"
        return "No resource selected"

    @rx.event
    def set_selected_resource(self, resource_id: str, resource_name: str = "Sample Resource", is_synced: bool = True):
        """Set the selected resource by ID."""
        if not self.check_authentication():
            return

        self.selected_resource_id = resource_id
        self.selected_resource_name = resource_name
        self.selected_resource_synced = is_synced

    @rx.event
    def sync_selected_resource(self):
        """Sync the selected resource to RAG."""
        if not self.check_authentication() or not self.selected_resource_id:
            return

        self.selected_resource_synced = True

    @rx.event
    def delete_selected_resource(self):
        """Delete the selected resource from RAG."""
        if not self.check_authentication() or not self.selected_resource_id:
            return

        self.selected_resource_synced = False
