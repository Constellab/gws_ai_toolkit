from typing import Literal

import reflex as rx
from gws_ai_toolkit.rag.common.rag_resource import RagResource
from gws_core import Logger
from gws_reflex_main import ReflexMainState

from ..rag_config_state import RagConfigState


class SyncAllResourcesDialogState(rx.State):
    """State management for the sync all resources dialog functionality."""

    resources_to_sync: list[RagResource] = []
    resources_to_sync_dialog_opened: bool = False
    load_resources_is_loading: bool = False
    sync_resource_progress: int = -1
    sync_errors: list[str] = []
    sync_limit: int | None = None

    @rx.event
    def set_sync_limit(self, value: str):
        """Set the maximum number of resources to sync. Empty value means no limit."""
        value = (value or "").strip()
        if not value:
            self.sync_limit = None
            return
        try:
            limit = int(value)
        except ValueError:
            self.sync_limit = None
            return
        self.sync_limit = limit if limit > 0 else None

    @rx.var
    def sync_limit_input_value(self) -> str:
        """String value for the limit input field (empty when no limit is set)."""
        return "" if self.sync_limit is None else str(self.sync_limit)

    @rx.var
    def total_resources_to_sync(self) -> int:
        """Total number of resources available to sync, before applying the limit."""
        return len(self.resources_to_sync)

    def _get_limited_resources_to_sync(self) -> list[RagResource]:
        """Return the resources to sync, capped to the configured limit."""
        if self.sync_limit is not None and self.sync_limit > 0:
            return self.resources_to_sync[: self.sync_limit]
        return self.resources_to_sync

    @rx.var
    def count_resources_to_sync(self) -> int:
        if self.sync_limit is not None and self.sync_limit > 0:
            return min(self.sync_limit, len(self.resources_to_sync))
        return len(self.resources_to_sync)

    @rx.var
    def has_loaded_resources_to_sync(self) -> bool:
        return not self.load_resources_is_loading

    @rx.var
    def resources_sync_status(self) -> Literal["pending", "running", "done"]:
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
        config_state: RagConfigState
        async with self:
            self.resources_to_sync = []
            self.sync_resource_progress = -1
            self.sync_limit = None
            self.load_resources_is_loading = True
            config_state = await RagConfigState.get_instance(self)

        try:
            rag_service = await config_state.get_dataset_rag_app_service()

            resources_to_sync = rag_service.get_all_resource_to_sync()
            async with self:
                self.resources_to_sync = resources_to_sync
        finally:
            async with self:
                self.load_resources_is_loading = False

    @rx.event(background=True)
    async def sync_resources_to_rag(self):
        config_state: RagConfigState
        async with self:
            self.sync_resource_progress = 0
            self.sync_errors = []
            config_state = await RagConfigState.get_instance(self)
            main_state = await self.get_state(ReflexMainState)

        rag_service = await config_state.get_dataset_rag_app_service()

        for resource in self._get_limited_resources_to_sync():
            try:
                with await main_state.authenticate_user():
                    rag_service.send_resource_to_rag(resource, upload_options=None)

            except Exception as e:
                Logger.log_exception_stack_trace(e)
                async with self:
                    self.sync_errors.append(
                        f"Error syncing resource '{resource.resource_model.name}' {resource.resource_model.id}: {e}"
                    )

            async with self:
                self.sync_resource_progress += 1

    @rx.var
    async def get_compatible_resource_explanation(self) -> str:
        config_state = await RagConfigState.get_instance(self)
        rag_service = await config_state.get_dataset_rag_app_service()
        if not rag_service:
            return ""
        return rag_service.get_compatible_resource_explanation()
