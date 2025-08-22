from typing import Optional

import reflex as rx

from .main_state import RagAppState


class ConfigState(RagAppState):
    """State management for the configuration functionality."""

    # Resource selection and management
    selected_resource_id: Optional[str] = None
    selected_resource_name: str = ""
    selected_resource_synced: bool = False

    # Operation status
    is_syncing: bool = False
    is_unsyncing: bool = False
    is_deleting: bool = False
    operation_progress: int = 0
    operation_message: str = ""
    operation_error: str = ""

    # Dialog states
    show_sync_all_dialog: bool = False
    show_unsync_all_dialog: bool = False
    show_delete_expired_dialog: bool = False

    # Simple counters for processing
    resources_to_sync_count: int = 0
    resources_to_unsync_count: int = 0
    documents_to_delete_count: int = 0

    @rx.var
    def get_selected_resource_info(self) -> str:
        """Get info about the currently selected resource."""
        if self.selected_resource_id:
            status = "synced" if self.selected_resource_synced else "not synced"
            return f"{self.selected_resource_name} - {status}"
        return "No resource selected"

    @rx.var
    def get_operation_status(self) -> str:
        """Get current operation status message."""
        if self.is_syncing:
            return f"Syncing resources... {self.operation_progress}%"
        elif self.is_unsyncing:
            return f"Unsyncing resources... {self.operation_progress}%"
        elif self.is_deleting:
            return f"Deleting documents... {self.operation_progress}%"
        return self.operation_message

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

        self.is_syncing = True
        self.operation_error = ""
        self.operation_message = "Resource synced successfully (simulated)"
        self.selected_resource_synced = True
        self.is_syncing = False

    @rx.event
    def delete_selected_resource(self):
        """Delete the selected resource from RAG."""
        if not self.check_authentication() or not self.selected_resource_id:
            return

        self.is_deleting = True
        self.operation_error = ""
        self.operation_message = "Resource deleted successfully (simulated)"
        self.selected_resource_synced = False
        self.is_deleting = False

    @rx.event
    def start_sync_all(self):
        """Start syncing all resources."""
        if not self.check_authentication():
            return

        self.is_syncing = True
        self.operation_error = ""
        self.show_sync_all_dialog = False
        self.operation_progress = 100
        self.operation_message = "All resources synced successfully (simulated)"
        self.is_syncing = False

    @rx.event
    def start_unsync_all(self):
        """Start unsyncing all resources."""
        if not self.check_authentication():
            return

        self.is_unsyncing = True
        self.operation_error = ""
        self.show_unsync_all_dialog = False
        self.operation_progress = 100
        self.operation_message = "All resources unsynced successfully (simulated)"
        self.is_unsyncing = False

    @rx.event
    def start_delete_expired(self):
        """Start deleting expired documents."""
        if not self.check_authentication():
            return

        self.is_deleting = True
        self.operation_error = ""
        self.show_delete_expired_dialog = False
        self.operation_progress = 100
        self.operation_message = "Expired documents deleted successfully (simulated)"
        self.is_deleting = False

    # Dialog control events
    @rx.event
    def show_sync_all_confirm(self):
        """Show sync all confirmation dialog."""
        self.show_sync_all_dialog = True

    @rx.event
    def hide_sync_all_confirm(self):
        """Hide sync all confirmation dialog."""
        self.show_sync_all_dialog = False

    @rx.event
    def show_unsync_all_confirm(self):
        """Show unsync all confirmation dialog."""
        self.show_unsync_all_dialog = True

    @rx.event
    def hide_unsync_all_confirm(self):
        """Hide unsync all confirmation dialog."""
        self.show_unsync_all_dialog = False

    @rx.event
    def show_delete_expired_confirm(self):
        """Show delete expired confirmation dialog."""
        self.show_delete_expired_dialog = True

    @rx.event
    def hide_delete_expired_confirm(self):
        """Hide delete expired confirmation dialog."""
        self.show_delete_expired_dialog = False

    @rx.event
    def clear_messages(self):
        """Clear operation messages."""
        self.operation_message = ""
        self.operation_error = ""
