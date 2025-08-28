from typing import Any, Dict, List

from gws_ai_toolkit.rag.common.base_rag_app_service import BaseRagAppService
from gws_core import ResourceModel, ResourceSearchBuilder, Tag


class TagRagAppService(BaseRagAppService):
    """
    Service used in the RagApp to store documents in a Rag.

    Any compatible document with the tag "send_to_rag" will be synced to the RAG platform.
    """

    SEND_TO_RAG_KEY = "send_to_rag"
    SEND_TO_RAG_VALUE = "true"

    def get_sync_to_rag_tag(self) -> Tag:
        return Tag(self.SEND_TO_RAG_KEY, self.SEND_TO_RAG_VALUE)

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
