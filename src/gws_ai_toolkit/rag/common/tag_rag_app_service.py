from typing import Any

from gws_core import EntityTagList, ResourceModel, ResourceSearchBuilder, Tag, TagEntityType

from gws_ai_toolkit.rag.common.base_rag_app_service import BaseRagAppService
from gws_ai_toolkit.rag.common.base_rag_service import BaseRagService
from gws_ai_toolkit.rag.common.rag_resource import RagResource
from gws_ai_toolkit.services.community_resource_files_manager_service import (
    CommunityResourceFilesManagerService,
)


class TagRagAppService(BaseRagAppService):
    """
    Service used in the RagApp to store documents in a Rag.

    Any compatible document with the tag specified in config will be synced to the RAG platform.
    """

    tag_key: str
    tag_value: str

    def __init__(
        self,
        rag_service: BaseRagService,
        dataset_id: str,
        additional_config: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(rag_service, dataset_id)
        if additional_config is None:
            additional_config = {}

        if "tag_key" not in additional_config:
            raise ValueError("tag_key must be provided in additional_config")
        if "tag_value" not in additional_config:
            raise ValueError("tag_value must be provided in additional_config")

        self.tag_key = additional_config["tag_key"]
        self.tag_value = additional_config["tag_value"]

    def get_sync_to_rag_tag(self) -> Tag:
        return Tag(self.tag_key, self.tag_value)

    def get_all_resources_to_send_to_rag(self) -> list[ResourceModel]:
        """
        Get all resources compatible with the RAG platform.
        It return only resources store in folder in datahub.
        """
        research_search = ResourceSearchBuilder()
        research_search.add_tag_filter(self.get_sync_to_rag_tag())
        research_search.add_is_fs_node_filter()
        research_search.add_is_archived_filter(False)

        return research_search.search_all()

    def get_chat_default_filters(self) -> dict[str, Any]:
        """Get the default inputs for the chat. This can be used to filter chat response."""
        return {}

    def get_compatible_resource_explanation(self) -> str:
        """Get a text explaining how the filtration is done."""
        text = super().get_compatible_resource_explanation()
        text += f"\n- Have the tag '{self.get_sync_to_rag_tag()}'"
        text += "\n- Not be archived"
        return text

    def count_synced_resources(self) -> int:
        """
        Count the number of resources that were synced to the RAG.
        This includes all resources that match the RAG criteria (tag, fs_node, not archived)
        and have been successfully synced to the RAG platform.

        Returns:
            int: The count of synced resources
        """
        research_search = ResourceSearchBuilder()
        research_search.add_tag_filter(self.get_sync_to_rag_tag())
        research_search.add_tag_key_filter(RagResource.RAG_SYNC_TAG_KEY)

        return research_search.build_search().count()

    def get_resources_marked_for_deletion(self) -> list[ResourceModel]:
        """
        Get all resources that are marked for deletion (have delete_in_next_sync tag).

        Returns:
            list[ResourceModel]: Resources marked for deletion
        """
        delete_tag = Tag(
            key=CommunityResourceFilesManagerService.DELETE_IN_NEXT_SYNC_TAG_KEY,
            value=CommunityResourceFilesManagerService.DELETE_IN_NEXT_SYNC_TAG_VALUE,
        )

        research_search = ResourceSearchBuilder()
        research_search.add_tag_filter(delete_tag)
        research_search.add_tag_filter(self.get_sync_to_rag_tag())  # Only resources with our target tag

        return research_search.search_all()

    def is_resource_marked_for_deletion(self, resource_model: ResourceModel) -> bool:
        """
        Check if a resource is marked for deletion.

        Args:
            resource_model: The resource to check

        Returns:
            bool: True if marked for deletion
        """
        resource_tags = EntityTagList.find_by_entity(TagEntityType.RESOURCE, resource_model.id)
        delete_tag = resource_tags.get_first_tag_by_key(
            CommunityResourceFilesManagerService.DELETE_IN_NEXT_SYNC_TAG_KEY
        )

        return (
            delete_tag is not None
            and delete_tag.get_tag_value()
            == CommunityResourceFilesManagerService.DELETE_IN_NEXT_SYNC_TAG_VALUE
        )

    def delete_resource_from_rag_and_lab(
        self, resource_model: ResourceModel, rag_service: BaseRagService, dataset_id: str
    ) -> dict[str, Any]:
        """
        Delete a resource from both RagFlow and the lab.

        Args:
            resource_model: The resource to delete
            rag_service: The RAG service to use for deletion
            dataset_id: The dataset ID where the document is stored

        Returns:
            dict: Deletion result with status and details
        """
        result = {
            "resource_id": resource_model.id,
            "resource_name": None,
            "deleted_from_rag": False,
            "deleted_from_lab": False,
            "error": None,
        }

        try:
            # Get resource name
            file_resource = resource_model.get_resource()
            result["resource_name"] = file_resource.name or resource_model.id

            # Create RagResource wrapper to check if synced
            rag_resource = RagResource(resource_model)

            # Delete from RagFlow if it was synced
            if rag_resource.is_synced_with_rag():
                try:
                    document_id = rag_resource.get_document_id()
                    resource_tags = EntityTagList.find_by_entity(
                        TagEntityType.RESOURCE, resource_model.id
                    )
                    dataset_id_tag = resource_tags.get_first_tag_by_key(
                        RagResource.RAG_DATASET_ID_TAG_KEY
                    )
                    rag_dataset_id = (
                        dataset_id_tag.get_tag_value() if dataset_id_tag else dataset_id
                    )

                    rag_service.delete_document(rag_dataset_id, document_id)
                    result["deleted_from_rag"] = True
                except Exception as e:
                    result["error"] = f"Could not delete from RagFlow: {str(e)}"

            # Delete the resource from the lab
            resource_model.delete_instance()
            result["deleted_from_lab"] = True

        except Exception as e:
            result["error"] = str(e)

        return result
