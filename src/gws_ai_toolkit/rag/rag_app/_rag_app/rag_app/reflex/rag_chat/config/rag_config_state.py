
from typing import Awaitable, Callable, Optional, cast

import reflex as rx
from gws_core import BaseModelDTO, Credentials, CredentialsDataOther, Logger

from gws_ai_toolkit.rag.common.base_rag_app_service import BaseRagAppService
from gws_ai_toolkit.rag.common.rag_app_service_factory import \
    RagAppServiceFactory
from gws_ai_toolkit.rag.common.rag_enums import (RagProvider,
                                                 RagResourceSyncMode)
from gws_ai_toolkit.rag.common.rag_service_factory import RagServiceFactory


class RagConfigStateConfig(BaseModelDTO):
    rag_provider: RagProvider
    resource_sync_mode: RagResourceSyncMode
    dataset_id: Optional[str]
    dataset_credentials_name: Optional[str]
    chat_id: Optional[str]
    chat_credentials_name: Optional[str]


class RagConfigState(rx.State):
    """State to configure the RAG (Retrieval-Augmented Generation) settings.
    """

    _config: RagConfigStateConfig
    _credentials: CredentialsDataOther

    _loader: Callable[[rx.State], Awaitable[RagConfigStateConfig]] | None = None

    @classmethod
    def set_loader(cls, loader: Callable[[rx.State], Awaitable[RagConfigStateConfig]]) -> None:
        """Set the loader function to get the path of the config file."""
        cls._loader = loader

    async def _get_config(self) -> RagConfigStateConfig:
        """Get the RAG configuration."""
        if not self._config:
            if RagConfigState._loader:
                self._config = await RagConfigState._loader(self)
            else:
                Logger.warning(
                    "RagConfigState loader is not set. Using default configuration. This is normal during compilation")
                return RagConfigStateConfig(
                    rag_provider='ragflow',
                    resource_sync_mode='tag',
                    dataset_id=None,
                    chat_id=None,
                    dataset_credentials_name=None,
                    chat_credentials_name=None,
                )

        return self._config

    async def get_rag_provider(self) -> RagProvider:
        """Get the RAG provider."""
        return self._config.rag_provider

    async def get_dataset_id(self) -> Optional[str]:
        """Get the dataset ID."""
        return self._config.dataset_id

    async def get_chat_id(self) -> Optional[str]:
        """Get the chat ID."""
        return self._config.chat_id

    async def get_resource_sync_mode(self) -> RagResourceSyncMode:
        """Get the resource sync mode."""
        return self._config.resource_sync_mode

    async def get_dataset_credentials(self) -> Optional[CredentialsDataOther]:
        """Get the dataset credentials."""
        if not self._credentials:
            config = await self._get_config()
            if not config.dataset_credentials_name:
                return None
            ds_creds = Credentials.find_by_name_and_check(config.dataset_credentials_name)
            self._credentials = cast(CredentialsDataOther, ds_creds.get_data_object())

        return self._credentials

    async def get_chat_credentials(self) -> Optional[CredentialsDataOther]:
        """Get the chat credentials."""
        if not self._credentials:
            config = await self._get_config()
            if not config.chat_credentials_name:
                return None
            chat_creds = Credentials.find_by_name_and_check(config.chat_credentials_name)
            self._credentials = cast(CredentialsDataOther, chat_creds.get_data_object())

        return self._credentials

    def set_config(self, config: RagConfigStateConfig):
        """Set the RAG configuration."""
        self._config = config

    async def get_dataset_rag_app_service(self) -> Optional[BaseRagAppService]:
        """Get the DataHub RAG service for dataset operations."""
        credentials = await self.get_dataset_credentials()
        if not credentials:
            return None
        return await self._build_rag_app_service(credentials)

    async def get_chat_rag_app_service(self) -> Optional[BaseRagAppService]:
        """Get the DataHub RAG service for chat operations."""
        credentials = await self.get_chat_credentials()
        if not credentials:
            return None
        return await self._build_rag_app_service(credentials)

    async def _build_rag_app_service(self, credentials: CredentialsDataOther) -> Optional[BaseRagAppService]:
        """Build a RAG app service."""
        provider = await self.get_rag_provider()
        if not provider:
            return None
        rag_service = RagServiceFactory.create_service(provider, credentials)

        return RagAppServiceFactory.create_service(await self.get_resource_sync_mode(),
                                                   rag_service, await self.get_dataset_id())
