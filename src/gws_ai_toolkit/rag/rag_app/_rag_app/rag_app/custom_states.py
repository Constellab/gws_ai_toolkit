
import reflex as rx

from .rag_main_state import RagAppState
from .reflex.core.app_config_state import AppConfigState
from .reflex.history.conversation_history_state import ConversationHistoryState
from .reflex.rag_chat.config.rag_config_state import RagConfigState, RagConfigStateConfig


class CustomAppConfigState(AppConfigState, rx.State):

    async def _get_config_file_path(self) -> str:
        base_state = await self.get_state(RagAppState)
        config = await base_state.get_param('configuration_file_path')
        return config or ''


class CustomConversationHistoryState(ConversationHistoryState, rx.State):

    async def _get_history_file_path_param(self) -> str:
        base_state = await self.get_state(RagAppState)
        config = await base_state.get_param('history_file_path')
        return config or ''


class CustomRagConfigState(RagConfigState, rx.State):

    async def _get_rag_config_data(self) -> RagConfigStateConfig:
        base_state = await self.get_state(RagAppState)
        params = await base_state.get_params()
        return RagConfigStateConfig(
            rag_provider=params.get("rag_provider"),
            resource_sync_mode=params.get("resource_sync_mode"),
            dataset_id=params.get("dataset_id"),
            dataset_credentials_name=params.get("dataset_credentials_name"),
            chat_id=params.get("chat_id"),
            chat_credentials_name=params.get("chat_credentials_name"),
        )
