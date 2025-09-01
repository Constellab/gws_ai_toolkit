from typing import List, Literal

import reflex as rx
from gws_core import AuthenticateUser

from gws_ai_toolkit.rag.common.rag_resource import RagResource
from gws_ai_toolkit.rag.rag_app._rag_app.rag_app.states.rag_main_state import \
    RagAppState


class SyncAllResourcesDialogState(RagAppState):
    """State management for the sync all resources dialog functionality."""

    resources_to_sync: List[RagResource] = []
    resources_to_sync_dialog_opened: bool = False
    sync_resource_progress: int = -1
    sync_errors: List[str] = []

    @rx.var
    def count_resources_to_sync(self) -> int:
        return len(self.resources_to_sync)

    @rx.var(cache=False)
    def has_loaded_resources_to_sync(self) -> bool:
        return self.resources_to_sync is not None

    @rx.var
    def resources_sync_status(self) -> Literal['pending', 'running', 'done']:
        if self.sync_resource_progress < 0:
            return "pending"
        elif self.sync_resource_progress < self.count_resources_to_sync:
            return "running"
        return "done"

    @rx.var
    def get_resource_sync_progress_percent(self) -> int:
        if self.count_resources_to_sync <= 0:
            return 0
        return int(self.sync_resource_progress / self.count_resources_to_sync * 100)

    @rx.event
    def open_dialog(self):
        self.resources_to_sync_dialog_opened = True

    @rx.event
    def close_dialog(self):
        """Close the resources to sync dialog."""
        self.resources_to_sync_dialog_opened = False

    @rx.event(background=True)
    async def on_sync_resource_dialog_event(self, opened: bool):
        """Handle dialog open event to load resources."""
        if opened:
            await self.load_resources_to_sync()
        # else:

    async def load_resources_to_sync(self):
        """Load resources to sync."""
        if not await self.check_authentication():
            raise Exception("User not authenticated")

        async with self:
            self.resources_to_sync = []
            self.sync_resource_progress = -1

        rag_service = await self.get_dataset_rag_app_service

        resources_to_sync = rag_service.get_all_resource_to_sync()
        async with self:
            self.resources_to_sync = resources_to_sync

    @rx.event(background=True)
    async def sync_resources_to_rag(self):
        async with self:
            self.sync_resource_progress = 0
            self.sync_errors = []

        rag_service = await self.get_dataset_rag_app_service

        for resource in self.resources_to_sync:

            try:
                with AuthenticateUser(await self.get_and_check_current_user()):
                    rag_service.send_resource_to_rag(resource,
                                                     upload_options=None)

            except Exception as e:
                async with self:
                    self.sync_errors.append(
                        f"Error syncing resource '{resource.resource_model.name}' {resource.resource_model.id}: {e}")

            async with self:
                self.sync_resource_progress += 1

    @rx.var
    async def get_compatible_resource_explanation(self) -> str:
        rag_service = await self.get_dataset_rag_app_service
        if not rag_service:
            return ""
        return rag_service.get_compatible_resource_explanation()
