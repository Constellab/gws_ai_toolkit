from typing import Optional

import reflex as rx
from gws_core import Credentials, CredentialsDataOther
from gws_reflex_main import ReflexMainState

from gws_ai_toolkit.rag.common.rag_datahub_service import DatahubRagService
from gws_ai_toolkit.rag.common.rag_enums import RagProvider
from gws_ai_toolkit.rag.common.rag_service_factory import RagServiceFactory


class RagAppState(ReflexMainState):
    """Main state for the RAG application with authentication and credential management."""

    # Internal state
    _chat_credentials: Optional[CredentialsDataOther] = None
    _knowledge_base_credentials: Optional[CredentialsDataOther] = None

    @rx.var
    def get_chat_credentials(self) -> Optional[CredentialsDataOther]:
        """Get the chat credentials."""
        if not self._chat_credentials:
            chat_credentials_name = self.get_param('chat_credentials_name')
            if not chat_credentials_name:
                return None
            chat_creds = Credentials.find_by_name_and_check(chat_credentials_name)
            self._chat_credentials = chat_creds.get_data_object()

        return self._chat_credentials

    @rx.var
    def get_knowledge_base_credentials(self) -> Optional[CredentialsDataOther]:
        """Get the knowledge base credentials."""
        if not self._knowledge_base_credentials:
            knowledge_base_credentials_name = self.get_param('knowledge_base_credentials_name')
            if not knowledge_base_credentials_name:
                return None
            kb_creds = Credentials.find_by_name_and_check(knowledge_base_credentials_name)
            self._knowledge_base_credentials = kb_creds.get_data_object()

        return self._knowledge_base_credentials

    @rx.var
    def get_rag_provider(self) -> Optional[RagProvider]:
        """Get the RAG provider."""
        return self.get_param('rag_provider')

    @rx.var
    def get_knowledge_base_id(self) -> str:
        """Get the knowledge base ID."""
        return self.get_param('knowledge_base_id', '')

    @rx.var
    def is_filter_rag_with_user_folders(self) -> bool:
        """Check if RAG should be filtered with user folders."""
        return self.get_param('filter_rag_with_user_folders', False)

    @rx.var
    def get_root_folder_limit(self) -> int:
        """Get the root folder limit."""
        return self.get_param('root_folder_limit', 0)

    @rx.var
    def get_chat_id(self) -> str:
        """Get the chat ID."""
        return self.get_param('chat_id', '')

    @rx.var
    def get_datahub_knowledge_rag_service(self) -> Optional[DatahubRagService]:
        """Get the DataHub RAG service for knowledge base operations."""
        provider = self.get_rag_provider
        if not provider:
            return None
        rag_service = RagServiceFactory.create_service(provider, self.get_knowledge_base_credentials)
        return DatahubRagService(rag_service, self.get_knowledge_base_id)

    @rx.var
    def get_datahub_chat_rag_service(self) -> Optional[DatahubRagService]:
        """Get the DataHub RAG service for chat operations."""
        provider = self.get_rag_provider
        if not provider:
            return None
        rag_service = RagServiceFactory.create_service(provider, self.get_chat_credentials)
        return DatahubRagService(rag_service, self.get_chat_id)
