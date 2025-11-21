
import reflex as rx
from gws_reflex_main import ReflexMainState

from .reflex.core.app_config_state import AppConfigState


class CustomAppConfigState(AppConfigState, rx.State):

    _chat_app_name: str = ''

    async def _get_config_file_path(self) -> str:
        base_state = await self.get_state(ReflexMainState)
        config = await base_state.get_param('configuration_file_path')
        return config or ''
