from typing import Optional

import reflex as rx
from gws_core import Credentials, CredentialsDataOther
from gws_reflex_main import ReflexMainState

from gws_ai_toolkit.rag.common.base_rag_app_service import BaseRagAppService
from gws_ai_toolkit.rag.common.rag_app_service_factory import \
    RagAppServiceFactory
from gws_ai_toolkit.rag.common.rag_enums import (RagProvider,
                                                 RagResourceSyncMode)
from gws_ai_toolkit.rag.common.rag_service_factory import RagServiceFactory


class RagAppState(ReflexMainState):
    """Main state for the RAG application with authentication and credential management."""

    # Internal state
    _chat_credentials: Optional[CredentialsDataOther] = None
    _dataset_credentials: Optional[CredentialsDataOther] = None

    @rx.var
    async def get_chat_credentials(self) -> Optional[CredentialsDataOther]:
        """Get the chat credentials."""
        if not self._chat_credentials:
            chat_credentials_name = await self.get_param('chat_credentials_name')
            if not chat_credentials_name:
                return None
            chat_creds = Credentials.find_by_name_and_check(chat_credentials_name)
            self._chat_credentials = chat_creds.get_data_object()

        return self._chat_credentials

    @rx.var
    async def get_dataset_credentials(self) -> Optional[CredentialsDataOther]:
        """Get the dataset credentials."""
        if not self._dataset_credentials:
            dataset_credentials_name = await self.get_param('dataset_credentials_name')
            if not dataset_credentials_name:
                return None
            ds_creds = Credentials.find_by_name_and_check(dataset_credentials_name)
            self._dataset_credentials = ds_creds.get_data_object()

        return self._dataset_credentials

    @rx.var
    async def get_rag_provider(self) -> Optional[RagProvider]:
        """Get the RAG provider."""
        return await self.get_param('rag_provider')

    @rx.var
    async def get_resource_sync_mode(self) -> Optional[RagResourceSyncMode]:
        return await self.get_param('resource_sync_mode')

    @rx.var
    async def get_dataset_id(self) -> str:
        """Get the dataset ID."""
        return await self.get_param('dataset_id', '')

    @rx.var
    async def get_chat_id(self) -> str:
        """Get the chat ID."""
        return await self.get_param('chat_id', '')

    @rx.var
    def super(self) -> int:
        return 7

    @rx.var
    async def get_dataset_rag_app_service(self) -> Optional[BaseRagAppService]:
        """Get the DataHub RAG service for dataset operations."""
        credentials = await self.get_dataset_credentials
        return await self._build_rag_app_service(credentials)

    @rx.var
    async def get_chat_rag_app_service(self) -> Optional[BaseRagAppService]:
        """Get the DataHub RAG service for chat operations."""
        credentials = await self.get_chat_credentials
        return await self._build_rag_app_service(credentials)

    async def _build_rag_app_service(self, credentials: CredentialsDataOther) -> Optional[BaseRagAppService]:
        """Build a RAG app service."""
        provider = await self.get_rag_provider
        if not provider:
            return None
        rag_service = RagServiceFactory.create_service(provider, credentials)

        return RagAppServiceFactory.create_service(await self.get_resource_sync_mode,
                                                   rag_service, await self.get_dataset_id)
