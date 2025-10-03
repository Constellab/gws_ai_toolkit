from typing import Any, Dict, List

from gws_ai_toolkit.rag.common.base_rag_app_service import BaseRagAppService
from gws_ai_toolkit.rag.common.base_rag_service import BaseRagService
from gws_core import ResourceModel, ResourceSearchBuilder, Tag


class TagRagAppService(BaseRagAppService):
    """
    Service used in the RagApp to store documents in a Rag.

    Any compatible document with the tag specified in config will be synced to the RAG platform.
    """

    tag_key: str
    tag_value: str

    def __init__(self, rag_service: BaseRagService, dataset_id: str, additional_config: Dict[str, Any] = None) -> None:
        if additional_config is None:
            additional_config = {}

        if 'tag_key' not in additional_config:
            raise ValueError("tag_key must be provided in additional_config")
        if 'tag_value' not in additional_config:
            raise ValueError("tag_value must be provided in additional_config")

        self.tag_key = additional_config['tag_key']
        self.tag_value = additional_config['tag_value']

        super().__init__(rag_service, dataset_id)

    def get_sync_to_rag_tag(self) -> Tag:
        return Tag(self.tag_key, self.tag_value)

    def get_all_resources_to_send_to_rag(self) -> List[ResourceModel]:
        """
        Get all resources compatible with the RAG platform.
        It return only resources store in folder in datahub.
        """
        research_search = ResourceSearchBuilder()
        research_search.add_tag_filter(self.get_sync_to_rag_tag())
        research_search.add_is_fs_node_filter()
        research_search.add_is_archived_filter(False)

        return research_search.search_all()

    def get_chat_default_filters(self) -> Dict[str, Any]:
        """Get the default inputs for the chat. This can be used to filter chat response.
        """
        return {}

    def get_compatible_resource_explanation(self) -> str:
        """Get a text explaining how the filtration is done.
        """
        text = super().get_compatible_resource_explanation()
        text += f"\n- Have the tag '{self.get_sync_to_rag_tag()}'"
        text += "\n- Not be archived"
        return text
