import reflex as rx
from gws_ai_toolkit._app.ai_rag import AppConfigState
from gws_reflex_main import ReflexMainState


class CustomAppConfigState(AppConfigState, rx.State):

    async def _get_config_file_path(self) -> str:
        base_state = await self.get_state(ReflexMainState)
        config = await base_state.get_param('configuration_file_path')
        return config or ''
