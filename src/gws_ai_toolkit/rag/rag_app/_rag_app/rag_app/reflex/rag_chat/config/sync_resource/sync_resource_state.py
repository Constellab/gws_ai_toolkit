from typing import List, Optional

import reflex as rx
from gws_core import (AuthenticateUser, BaseModelDTO, Logger, ResourceModel,
                      ResourceSearchBuilder)

from gws_ai_toolkit.rag.common.rag_models import RagDocument
from gws_ai_toolkit.rag.common.rag_resource import RagResource

from ..rag_config_state import RagConfigState


class ResourceDTO(BaseModelDTO):
    id: str
    name: str


class SyncResourceState(rx.State):

    text: str = ""

    popover_opened: bool = False
    hover_index: int = 0

    _resources: List[ResourceModel] = []
    _selected_resource: RagResource | None = None
    selected_resource_document: Optional[RagDocument] = None

    send_to_rag_is_loading: bool = False
    delete_from_rag_is_loading: bool = False
    parse_document_is_loading: bool = False

    @rx.event(background=True)
    async def set_text(self, text: str):
        async with self:
            self.text = text
            self._selected_resource = None
            self.hover_index = 0

        resource_search_builder = ResourceSearchBuilder()
        resource_search_builder.add_name_filter(self.text)
        resources = resource_search_builder.search_all()

        async with self:
            self._resources = resources

    def on_input_focus(self):
        self.popover_opened = True

    def on_input_key_down(self, event: str):
        if event == "Enter":
            # select current hovered resource
            resource = self._resources[self.hover_index]
            if resource:
                self.select_resource(resource.id)
        elif event == "ArrowDown":
            self._update_hover_index(1)
        elif event == "ArrowUp":
            self._update_hover_index(-1)

    def _update_hover_index(self, shift: int):
        new_index = self.hover_index + shift
        if new_index < 0:
            new_index = len(self._resources) - 1
        elif new_index >= len(self._resources):
            new_index = 0
        self.hover_index = new_index

    @rx.var
    def resources_infos(self) -> List[ResourceDTO]:
        return [ResourceDTO(id=resource.id, name=resource.name) for resource in self._resources]

    @rx.var
    def no_resources_found(self) -> bool:
        return not self._resources

    @rx.var
    def selected_resource_info(self) -> ResourceDTO | None:
        if not self._selected_resource:
            return None
        return ResourceDTO(
            id=self._selected_resource.resource_model.id, name=self._selected_resource.resource_model.name)

    @rx.event(background=True)
    async def select_resource(self, resource_id: str):
        resource = next((r for r in self._resources if r.id == resource_id), None)
        if resource:
            async with self:
                self._selected_resource = RagResource(resource)
                self.popover_opened = False
                self.text = resource.name
                self.selected_resource_document = None

            await self._load_rag_document(self._selected_resource)

    @rx.var
    def is_selected_resource_compatible(self) -> bool:
        """Check if the selected resource is compatible with RAG."""
        if not self._selected_resource:
            return False
        return self._selected_resource.is_compatible_with_rag()

    @rx.var
    def is_selected_resource_synced(self) -> bool:
        """Check if the selected resource is synced with RAG."""
        if not self._selected_resource:
            return False
        return self._selected_resource.is_synced_with_rag()

    @rx.var
    def selected_resource_dataset_id(self) -> str:
        """Get the dataset ID of the selected resource."""
        if not self._selected_resource or not self.is_selected_resource_synced:
            return ""
        try:
            return self._selected_resource.get_dataset_base_id()
        except:
            return ""

    @rx.var
    def selected_resource_document_id(self) -> str:
        """Get the document ID of the selected resource."""
        if not self._selected_resource or not self.is_selected_resource_synced:
            return ""
        try:
            return self._selected_resource.get_and_check_document_id()
        except:
            return ""

    @rx.var
    def selected_resource_sync_date(self) -> str:
        """Get the sync date of the selected resource."""
        if not self._selected_resource or not self.is_selected_resource_synced:
            return ""
        try:
            sync_date = self._selected_resource.get_and_check_sync_date()
            return sync_date.strftime("%Y-%m-%d %H:%M:%S UTC")
        except:
            return ""

    @rx.event(background=True)
    async def send_to_rag(self):
        """Send the selected resource to RAG."""
        if not self._selected_resource:
            return

        config_state: RagConfigState
        async with self:
            self.send_to_rag_is_loading = True
            config_state = await self.get_state(RagConfigState)

        try:
            rag_service = await config_state.get_dataset_rag_app_service()
            if rag_service:
                with AuthenticateUser(await config_state.get_and_check_current_user()):
                    rag_service.send_resource_to_rag(
                        self._selected_resource,
                        upload_options=None
                    )
        except Exception as e:
            Logger.log_exception_stack_trace(e)
            yield rx.toast.error(f"Failed to send resource to RAG: {e}", duration=3000)
            return
        finally:
            await self._refresh_selected_resource()
            async with self:
                self.send_to_rag_is_loading = False

        yield rx.toast.success("Resource sent to RAG successfully.", duration=3000)

    @rx.event(background=True)
    async def delete_from_rag(self):
        """Delete the selected resource from RAG."""
        if not self._selected_resource:
            return

        config_state: RagConfigState
        async with self:
            self.delete_from_rag_is_loading = True
            config_state = await self.get_state(RagConfigState)

        try:
            rag_service = await config_state.get_dataset_rag_app_service()
            if rag_service:
                with AuthenticateUser(await config_state.get_and_check_current_user()):
                    rag_service.delete_resource_from_rag(self._selected_resource)
        except Exception as e:
            Logger.log_exception_stack_trace(e)
            yield rx.toast.error(f"Failed to delete resource from RAG: {e}", duration=3000)
            return
        finally:
            await self._refresh_selected_resource()
            async with self:
                self.delete_from_rag_is_loading = False

        yield rx.toast.success("Resource deleted from RAG successfully.", duration=3000)

    @rx.event(background=True)
    async def parse_document(self):
        """Parse the selected resource document in RAG."""
        if not self._selected_resource or not self.is_selected_resource_synced:
            return

        config_state: RagConfigState
        async with self:
            self.parse_document_is_loading = True
            config_state = await self.get_state(RagConfigState)

        try:
            dataset_id = self.selected_resource_dataset_id
            document_id = self.selected_resource_document_id

            rag_app_service = await config_state.get_dataset_rag_app_service()
            if dataset_id and document_id and rag_app_service:
                with AuthenticateUser(await config_state.get_and_check_current_user()):
                    rag_service = rag_app_service.get_rag_service()
                    parsed_document = rag_service.parse_document(
                        dataset_id, document_id
                    )
                    async with self:
                        self.selected_resource_document = parsed_document
        except Exception as e:
            Logger.log_exception_stack_trace(e)
            yield rx.toast.error(f"Failed to parse document: {e}", duration=3000)
            return
        finally:
            async with self:
                self.parse_document_is_loading = False

        yield rx.toast.success("Document parsing initiated successfully.", duration=3000)

    @rx.event(background=True)
    async def refresh_selected_resource(self):
        """Refresh the selected resource information."""
        await self._refresh_selected_resource()

    async def _refresh_selected_resource(self):
        if not self._selected_resource:
            return

        resource = ResourceModel.get_by_id_and_check(self._selected_resource.resource_model.id)

        async with self:
            self._selected_resource = RagResource(resource)

        await self._load_rag_document(self._selected_resource)

    async def _load_rag_document(self, selected_resource: RagResource):
        """Load the RAG document information."""

        config_state: RagConfigState
        async with self:
            # Also refresh document info if resource is synced
            self.selected_resource_document = None
            config_state = await self.get_state(RagConfigState)

        if selected_resource.is_synced_with_rag():
            dataset_id = self.selected_resource_dataset_id
            document_id = self.selected_resource_document_id

            rag_app_service = await config_state.get_dataset_rag_app_service()
            if selected_resource.get_dataset_base_id() and selected_resource.get_document_id() and rag_app_service:
                rag_service = rag_app_service.get_rag_service()
                document = rag_service.get_document(
                    dataset_id, document_id
                )

                async with self:
                    self.selected_resource_document = document
