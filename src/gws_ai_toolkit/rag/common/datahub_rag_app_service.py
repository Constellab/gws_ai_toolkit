from typing import Any

from gws_core import DataHubS3ServerService, ResourceModel, ResourceSearchBuilder, SpaceService

from gws_ai_toolkit.rag.common.base_rag_app_service import BaseRagAppService
from gws_ai_toolkit.rag.common.rag_resource import RagResource
from gws_ai_toolkit.rag.dify.rag_dify_service import RagDifyService

from .base_rag_service import BaseRagService


class DatahubRagAppService(BaseRagAppService):
    """
    Service used in the RagApp to store and manage datahub documents
    in the RAG platform.

    It only sync the document of the datahub (stored in a folder).
    In the Rag platform it stores the root folder id of the document as metadata.

    When a chat request is made, it load the current user root folders to filter the result only
    on document accessible by the user.

    This only works with Dify as other Rag doesn't support metadata filtering on chat.
    """

    # Use to cache the current user folders
    _current_user_folders_ids: list[str] = None

    # Common constants
    ROOT_FOLDER_ID_METADATA_KEY = "root_folder_id"
    CHAT_INPUT_ACCESS_KEY = "folder_"

    # Number max of folder supported by the filter
    FOLDER_LIMIT = 20

    def __init__(
        self, rag_service: BaseRagService, dataset_id: str, additional_config: dict[str, Any] = None
    ) -> None:
        if additional_config is None:
            additional_config = {}

        if not isinstance(rag_service, RagDifyService):
            raise ValueError("Only Dify Rag is compatible with the DatahubRagAppService")
        super().__init__(rag_service, dataset_id)

    def get_all_resources_to_send_to_rag(self) -> list[ResourceModel]:
        """
        Get all resources compatible with the RAG platform.
        It return only resources store in folder in datahub.
        """
        research_search = ResourceSearchBuilder()
        s3_service = DataHubS3ServerService.get_instance()
        research_search.add_tag_filter(s3_service.get_datahub_tag())
        research_search.add_is_fs_node_filter()
        research_search.add_is_archived_filter(False)
        research_search.add_has_folder_filter()

        return research_search.search_all()

    def get_chat_default_filters(self) -> dict[str, Any]:
        """Get the default inputs for the chat. This can be used to filter chat response."""
        # Load all the root folders of the current user
        if self._current_user_folders_ids is None:
            folders = SpaceService.get_instance().get_all_current_user_root_folders()
            if folders:
                folder_ids = [folder.id for folder in folders]

                # limit the number of folders
                if len(folder_ids) > self.FOLDER_LIMIT:
                    folder_ids = folder_ids[: self.FOLDER_LIMIT]
                self._current_user_folders_ids = folder_ids

        # Add folder filtering to inputs - this format depends on how the
        # underlying RAG platform handles folder-based filtering
        folder_filters = {}
        for i, folder_id in enumerate(self._current_user_folders_ids):
            folder_filters[f"{self.CHAT_INPUT_ACCESS_KEY}{i}"] = folder_id

        return folder_filters

    def get_document_metadata_before_sync(self, rag_resource: RagResource) -> dict[str, Any]:
        metadata = super().get_document_metadata_before_sync(rag_resource)

        # Add the root folder of the document as metadata
        root_folder = rag_resource.get_root_folder()
        if root_folder is None:
            raise ValueError(
                "The resource is not associated with a folder, it can't be synced with the rag."
            )
        metadata[self.ROOT_FOLDER_ID_METADATA_KEY] = root_folder.id

        return metadata

    def get_compatible_resource_explanation(self) -> str:
        """Get a text explaining how the filtration is done."""
        text = super().get_compatible_resource_explanation()
        s3_service = DataHubS3ServerService.get_instance()
        text += f"\n- Have the tag '{s3_service.get_datahub_tag()}'"
        text += "\n- Be in a folder"
        text += "\n- Not be archived"
        return text
