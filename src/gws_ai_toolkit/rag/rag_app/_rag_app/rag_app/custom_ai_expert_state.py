
from abc import abstractmethod
from dataclasses import dataclass
from typing import List

import reflex as rx
from gws_core import (BaseModelDTO, EntityTagList, Logger, ResourceModel,
                      ResourceSearchBuilder, TagEntityType)

from gws_ai_toolkit.rag.common.rag_resource import RagResource

from .reflex import AiExpertState, AiTableState
from .reflex.chat_base.base_file_analysis_state import BaseFileAnalysisState


@dataclass
class FullResourceDTO():
    is_in_rag: bool
    is_excel: bool
    rag_resource: RagResource


class ResourceDTO(BaseModelDTO):
    id: str
    name: str
    is_in_rag: bool = False
    is_excel: bool = False


class AssociatedResourceState(rx.State, mixin=True):

    _linked_resources: List[FullResourceDTO] = []

    @abstractmethod
    async def get_file_state(self) -> BaseFileAnalysisState:
        """Get the file analysis state instance."""
        pass

    async def load_linked_resources(self) -> None:

        if self._linked_resources:
            return

        file_state = await self.get_file_state()

        resource = await file_state.get_current_resource_model()

        if not resource:
            Logger.warning("No resource found in state")
            # self._linked_resources = []
            return

        tags = EntityTagList.find_by_entity(TagEntityType.RESOURCE, resource.id)

        study_tags = tags.get_tags_by_key("study")
        if not study_tags:
            Logger.warning("No study tag found on resource")
            # self._linked_resources = []
            return

        study_tag = study_tags[0].to_simple_tag()
        search_builder = ResourceSearchBuilder()
        search_builder.add_tag_filter(study_tag)
        search_builder.add_ordering(ResourceModel.name)

        resources: List[ResourceModel] = search_builder.search_all()
        linked_resources: List[FullResourceDTO] = []
        for res in resources:
            rag_resource = RagResource(res)
            linked_resources.append(FullResourceDTO(
                is_in_rag=rag_resource.is_synced_with_rag(),
                is_excel=rag_resource.get_raw_file().is_csv_or_excel(),
                rag_resource=rag_resource
            ))

        self._linked_resources = linked_resources

    @rx.var
    async def linked_resources_data(self) -> List[ResourceDTO]:
        return [
            ResourceDTO(
                id=res.rag_resource.get_id(),
                name=res.rag_resource.resource_model.name,
                is_in_rag=res.is_in_rag,
                is_excel=res.is_excel
            ) for res in self._linked_resources
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
        ai_expert_state = await self.get_file_state()
        return await ai_expert_state.open_document_from_resource(resource_id)


class CustomAssociatedResourceAiExpertState(AssociatedResourceState, rx.State):
    """Custom AI Expert state with associated resource functionality."""

    async def get_file_state(self) -> BaseFileAnalysisState:
        return await self.get_state(AiExpertState)


class CustomAssociatedResourceAiTableState(AssociatedResourceState, rx.State):
    """Custom AI Table state with associated resource functionality."""

    async def get_file_state(self) -> BaseFileAnalysisState:
        return await self.get_state(AiTableState)
