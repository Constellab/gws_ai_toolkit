from dataclasses import dataclass

import reflex as rx
from gws_ai_toolkit._app.ai_rag import AiExpertState
from gws_ai_toolkit.core.utils import Utils
from gws_ai_toolkit.rag.common.rag_resource import RagResource
from gws_core import (
    BaseModelDTO,
    EntityTagList,
    File,
    Logger,
    ResourceModel,
    ResourceSearchBuilder,
    Table,
    TagEntityType,
)
from gws_reflex_main import ReflexMainState


@dataclass
class FullResourceDTO:
    is_in_rag: bool
    is_table: bool
    resource: ResourceModel


class ResourceDTO(BaseModelDTO):
    id: str
    name: str
    is_in_rag: bool = False
    is_table: bool = False


class AssociatedResourcesState(rx.State):
    """State to manage the left section of the AI expert page.
    This load the associated resources of the selected resource.
    """

    is_loading: bool = False
    _linked_resources: list[FullResourceDTO] = []

    _current_resource_id: str | None = None
    is_dialog_open: bool = False

    @rx.event(background=True)  # type: ignore
    async def load_from_expert_state(self) -> None:
        async with self:
            expert_state = await self.get_state(AiExpertState)
            resource_model = await expert_state.get_current_resource_model()

        if not resource_model:
            return

        await self._load_for_resource(resource_model.id)

    @rx.event(background=True)  # type: ignore
    async def open_associated_resources_dialog(self, source_id: str) -> None:
        """Load linked resources based on a RAG source document ID."""

        async with self:
            self.is_dialog_open = True

        rag_resource = RagResource.from_document_or_resource_id_and_check(source_id)

        await self._load_for_resource(rag_resource.get_id())

    async def _load_for_resource(self, resource_id: str | None):
        if self.is_loading:
            return

        if not resource_id:
            async with self:
                self._current_resource_id = None
                self._linked_resources = []
            return

        async with self:
            self._current_resource_id = resource_id
            self.is_loading = True

        try:
            tags = EntityTagList.find_by_entity(TagEntityType.RESOURCE, resource_id)

            study_tags = tags.get_tags_by_key("study")
            if not study_tags:
                Logger.warning("No study tag found on resource")
                # self._linked_resources = []
                return

            study_tag = study_tags[0].to_simple_tag()
            search_builder = ResourceSearchBuilder()
            search_builder.add_tag_filter(study_tag)
            search_builder.add_ordering(ResourceModel.name)

            resource_models: list[ResourceModel] = search_builder.search_all()
            linked_resources: list[FullResourceDTO] = []
            for resource_model in resource_models:
                if resource_model.get_id() == resource_id:
                    continue

                is_in_rag = False
                is_table = False
                is_file = False
                resource_type = resource_model.get_resource_type()

                if resource_type and issubclass(resource_type, Table):
                    is_table = True

                if resource_type and issubclass(resource_type, File):
                    is_file = True
                    rag_resource = RagResource(resource_model)
                    is_in_rag = rag_resource.is_synced_with_rag()

                if not is_file and not is_table:
                    continue

                rag_resource = RagResource(resource_model)
                linked_resources.append(
                    FullResourceDTO(
                        is_in_rag=is_in_rag,
                        is_table=is_table,
                        resource=resource_model,
                    )
                )

            async with self:
                self._linked_resources = linked_resources
        finally:
            async with self:
                self.is_loading = False

    @rx.var
    async def linked_resources_data(self) -> list[ResourceDTO]:
        return [
            ResourceDTO(
                id=res.resource.id,
                name=res.resource.name,
                is_in_rag=res.is_in_rag,
                is_table=res.is_table,
            )
            for res in self._linked_resources
        ]

    @rx.event
    def open_ai_expert_from_resource(self, resource_id: str):
        """Redirect the user to the AI Expert page for a specific resource."""
        return rx.redirect(f"/ai-expert/{resource_id}")

    @rx.event
    def open_ai_table_from_resource(self, resource_id: str):
        """Redirect the user to the AI Table page for a specific Excel/CSV resource."""
        return rx.redirect(f"/ai-table/{resource_id}")

    @rx.event
    async def open_document_from_resource(self, resource_id: str):
        """Redirect the user to an external URL for a specific resource."""
        main_state = await self.get_state(ReflexMainState)

        with await main_state.authenticate_user():
            public_link = Utils.generate_temp_share_resource_link(resource_id)

        if public_link:
            # Redirect the user to the share link URL
            return rx.redirect(public_link, is_external=True)

    @rx.event
    def close_dialog(self):
        """Close the associated resources dialog."""
        self.is_dialog_open = False
