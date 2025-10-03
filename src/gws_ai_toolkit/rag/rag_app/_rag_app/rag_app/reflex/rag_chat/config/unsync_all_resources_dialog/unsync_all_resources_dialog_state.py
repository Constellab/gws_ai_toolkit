from typing import List, Literal

import reflex as rx
from gws_core import AuthenticateUser, Logger, User

from gws_ai_toolkit.rag.common.rag_resource import RagResource

from ..rag_config_state import RagConfigState


class UnsyncAllResourcesDialogState(rx.State):
    """State management for the unsync all resources dialog functionality."""

    resources_to_unsync: List[RagResource] = []
    resources_to_unsync_dialog_opened: bool = False
    unsync_resource_progress: int = -1
    unsync_errors: List[str] = []

    @rx.var
    def count_resources_to_unsync(self) -> int:
        return len(self.resources_to_unsync)

    @rx.var(cache=False)
    def has_loaded_resources_to_unsync(self) -> bool:
        return self.resources_to_unsync is not None

    @rx.var
    def resources_unsync_status(self) -> Literal['pending', 'running', 'done']:
        if self.unsync_resource_progress < 0:
            return "pending"
        elif self.unsync_resource_progress < self.count_resources_to_unsync:
            return "running"
        return "done"

    @rx.var
    def get_resource_unsync_progress_percent(self) -> int:
        if self.count_resources_to_unsync <= 0:
            return 0
        return int(self.unsync_resource_progress / self.count_resources_to_unsync * 100)

    @rx.event
    def open_dialog(self):
        self.resources_to_unsync_dialog_opened = True

    @rx.event
    def close_dialog(self):
        """Close the resources to unsync dialog."""
        self.resources_to_unsync_dialog_opened = False

    @rx.event(background=True)
    async def on_unsync_resource_dialog_event(self, opened: bool):
        """Handle dialog open event to load resources."""
        if opened:
            await self.load_resources_to_unsync()
        # else:

    async def load_resources_to_unsync(self):
        """Load resources to unsync."""
        config_state: RagConfigState
        async with self:
            self.resources_to_unsync = []
            self.unsync_resource_progress = -1
            config_state = await RagConfigState.get_instance(self)

        rag_service = await config_state.get_dataset_rag_app_service()

        resources_to_unsync = rag_service.get_all_synced_resources()
        async with self:
            self.resources_to_unsync = resources_to_unsync

    @rx.event(background=True)
    async def unsync_resources_from_rag(self):
        config_state: RagConfigState
        user: User
        async with self:
            self.unsync_resource_progress = 0
            self.unsync_errors = []
            config_state = await RagConfigState.get_instance(self)
            user = await config_state.get_and_check_current_user()

        rag_service = await config_state.get_dataset_rag_app_service()

        for resource in self.resources_to_unsync:

            try:
                with AuthenticateUser(user):
                    rag_service.delete_resource_from_rag(resource)

            except Exception as e:
                Logger.log_exception_stack_trace(e)
                async with self:
                    self.unsync_errors.append(
                        f"Error unsyncing resource '{resource.resource_model.name}' {resource.resource_model.id}: {e}")

            async with self:
                self.unsync_resource_progress += 1
