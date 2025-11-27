import reflex as rx
from gws_reflex_main import ReflexMainState

from .reflex.core.app_config_state import AppConfigState, AppConfigStateConfig


class CustomAppConfigState(AppConfigState, rx.State):
    async def _get_config(self) -> AppConfigStateConfig:
        base_state = await self.get_state(ReflexMainState)
        params = await base_state.get_params()
        return AppConfigStateConfig(
            configuration_file_path=params.get("configuration_file_path", ""),
            chat_app_name=params.get("chat_app_name", ""),
        )
