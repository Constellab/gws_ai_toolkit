from gws_ai_toolkit.rag.common.base_rag_app_service import BaseRagAppService
from gws_ai_toolkit.rag.common.datahub_rag_app_service import DatahubRagAppService
from gws_ai_toolkit.rag.common.tag_rag_app_service import TagRagAppService

from .base_rag_service import BaseRagService
from .rag_enums import RagResourceSyncMode


class RagAppServiceFactory:
    """Factory class to create RAG app services based on provider type."""

    @staticmethod
    def create_service(
        resource_mode: RagResourceSyncMode,
        rag_service: BaseRagService,
        dataset_id: str,
        additional_config: dict | None = None,
    ) -> BaseRagAppService:
        """Create the appropriate RAG app service based on RagResourceMode.

        Args:
            resource_mode: The RAG resource mode ('datahub' or 'tag')
            rag_service: The RAG service instance
            dataset_id: The dataset ID to use
            additional_config: Additional configuration dict for the service

        Returns:
            BaseRagAppService: Instance of the appropriate service

        Raises:
            ValueError: If provider is not supported
        """
        if additional_config is None:
            additional_config = {}

        if resource_mode == "tag":
            return TagRagAppService(rag_service, dataset_id, additional_config)
        elif resource_mode == "datahub":
            return DatahubRagAppService(rag_service, dataset_id, additional_config)
        else:
            raise ValueError(f"Unsupported RAG resource sync mode: {resource_mode}")
