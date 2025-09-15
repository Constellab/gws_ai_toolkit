import reflex as rx

from gws_ai_toolkit._app.core import AppConfigState
from gws_ai_toolkit._app.history import ConversationHistoryState

from .main_state import MainState


class CustomAppConfigState(AppConfigState, rx.State):

    async def _get_config_file_path(self) -> str:
        base_state = await self.get_state(MainState)
        config = await base_state.get_param('configuration_file_path')
        return config or ''


class CustomConversationHistoryState(ConversationHistoryState, rx.State):

    async def _get_history_folder_path_param(self) -> str:
        base_state = await self.get_state(MainState)
        config = await base_state.get_param('history_folder_path')
        return config or ''
