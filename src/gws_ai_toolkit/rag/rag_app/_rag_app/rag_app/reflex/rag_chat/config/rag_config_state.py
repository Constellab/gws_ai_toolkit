from abc import abstractmethod
from typing import Optional, cast

import reflex as rx
from gws_ai_toolkit.rag.common.base_rag_app_service import BaseRagAppService
from gws_ai_toolkit.rag.common.rag_app_service_factory import \
    RagAppServiceFactory
from gws_ai_toolkit.rag.common.rag_enums import (RagProvider,
                                                 RagResourceSyncMode)
from gws_ai_toolkit.rag.common.rag_service_factory import RagServiceFactory
from gws_core import BaseModelDTO, Credentials, CredentialsDataOther, User

from ...core.utils import Utils


class RagConfigStateConfig(BaseModelDTO):
    rag_provider: RagProvider
    resource_sync_mode: RagResourceSyncMode
    dataset_id: Optional[str]
    dataset_credentials_name: Optional[str]
    chat_id: Optional[str]
    chat_credentials_name: Optional[str]
    resource_tag_key: Optional[str]
    resource_tag_value: Optional[str]


class RagConfigState(rx.State, mixin=True):
    """State management for RAG configuration and service integration.

    This state class manages the configuration of RAG services, handling provider
    settings, credentials, dataset connections, and service instantiation. It serves
    as the central point for RAG system configuration and provides service instances
    to other components.

    Key Responsibilities:
        - RAG provider configuration (Dify, RagFlow)
        - Credentials management for external services
        - Dataset and chat service configuration
        - Service factory integration
        - Resource synchronization mode settings

    The state uses a mixin pattern for configuration and provides methods to
    instantiate configured RAG services for use throughout the application.
    """

    _rag_config: RagConfigStateConfig
    _credentials: CredentialsDataOther

    @abstractmethod
    async def _get_rag_config_data(self) -> RagConfigStateConfig:
        """Override this method to specify how to get RAG configuration."""
        pass

    async def get_rag_config(self) -> RagConfigStateConfig:
        """Get the RAG configuration."""
        if not self._rag_config:
            self._rag_config = await self._get_rag_config_data()
        return self._rag_config

    async def get_rag_provider(self) -> RagProvider:
        """Get the RAG provider."""
        config = await self.get_rag_config()
        return config.rag_provider

    async def get_dataset_id(self) -> Optional[str]:
        """Get the dataset ID."""
        config = await self.get_rag_config()
        return config.dataset_id

    async def get_chat_id(self) -> Optional[str]:
        """Get the chat ID."""
        config = await self.get_rag_config()
        return config.chat_id

    async def get_resource_sync_mode(self) -> RagResourceSyncMode:
        """Get the resource sync mode."""
        config = await self.get_rag_config()
        return config.resource_sync_mode

    async def get_dataset_credentials(self) -> Optional[CredentialsDataOther]:
        """Get the dataset credentials."""
        if not self._credentials:
            config = await self.get_rag_config()
            if not config.dataset_credentials_name:
                return None
            ds_creds = Credentials.find_by_name_and_check(config.dataset_credentials_name)
            self._credentials = cast(CredentialsDataOther, ds_creds.get_data_object())

        return self._credentials

    async def get_chat_credentials(self) -> Optional[CredentialsDataOther]:
        """Get the chat credentials."""
        if not self._credentials:
            config = await self.get_rag_config()
            if not config.chat_credentials_name:
                return None
            chat_creds = Credentials.find_by_name_and_check(config.chat_credentials_name)
            self._credentials = cast(CredentialsDataOther, chat_creds.get_data_object())

        return self._credentials

    def set_config(self, config: RagConfigStateConfig):
        """Set the RAG configuration."""
        self._rag_config = config

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

        dataset_id = await self.get_dataset_id()
        config = await self.get_rag_config()

        additional_config = {}
        if config.resource_tag_key:
            additional_config['tag_key'] = config.resource_tag_key
        if config.resource_tag_value:
            additional_config['tag_value'] = config.resource_tag_value

        return RagAppServiceFactory.create_service(await self.get_resource_sync_mode(),
                                                   rag_service, dataset_id or "", additional_config)

    @staticmethod
    async def get_instance(state: rx.State) -> 'RagConfigState':
        """Get the RagConfigState instance from any state."""

        config_state = await Utils.get_first_state_of_type(state, RagConfigState)

        if config_state:
            return config_state
        else:
            raise ValueError(
                "RagConfigState subclass not found. You must define a subclass of RagConfigState in your app to configure it.")
