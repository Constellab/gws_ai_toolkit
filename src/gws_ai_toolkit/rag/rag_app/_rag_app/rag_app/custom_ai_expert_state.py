
from dataclasses import dataclass
from typing import List

import reflex as rx
from gws_core import BaseModelDTO, Logger, ResourceModel, ResourceSearchBuilder

from gws_ai_toolkit.rag.common.rag_resource import RagResource

from .reflex import AiExpertState


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


class CustomAiExpertState(AiExpertState):

    _linked_resources: List[FullResourceDTO] = []

    async def load_resource_from_url(self):
        print('Loading resource from URL in CustomAiExpertState')
        parent_state = await self.get_state(AiExpertState)

        await parent_state.load_resource_from_url()

        current_resource = parent_state.get_current_rag_resource()
        if not current_resource:
            Logger.warning("No resource found in URL")
            return

        resource_tags = current_resource.get_tags()

        study_tags = resource_tags.get_tags_by_key("study")
        if not study_tags:
            Logger.warning("No study tag found on resource")
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
    def linked_resources_data(self) -> List[ResourceDTO]:
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
        return await super().open_document_from_resource(resource_id)
