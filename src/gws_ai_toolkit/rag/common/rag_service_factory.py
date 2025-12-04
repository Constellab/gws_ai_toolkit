from gws_core import CredentialsDataOther

from .base_rag_service import BaseRagService
from .rag_enums import RagProvider


class RagServiceFactory:
    """Factory class to create RAG services based on provider type."""

    @staticmethod
    def create_service(provider: RagProvider, credentials: CredentialsDataOther) -> BaseRagService:
        """Create the appropriate RAG service based on provider.

        Args:
            provider: The RAG provider type ('dify' or 'ragflow')
            credentials: Service credentials

        Returns:
            BaseRagService: Instance of the appropriate service

        Raises:
            ValueError: If provider is not supported
        """
        if provider == "dify":
            from ..dify.rag_dify_service import RagDifyService

            return RagDifyService.from_credentials(credentials)
        elif provider == "ragflow":
            from ..ragflow.rag_ragflow_service import RagRagFlowService

            return RagRagFlowService.from_credentials(credentials)
        else:
            raise ValueError(f"Unsupported RAG provider: {provider}")
