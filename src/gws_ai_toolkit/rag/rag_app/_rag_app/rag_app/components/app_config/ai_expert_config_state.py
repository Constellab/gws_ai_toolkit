import reflex as rx
from gws_core.core.utils.logger import Logger

from gws_ai_toolkit.rag.rag_app._rag_app.rag_app.components.app_config.ai_expert_config import \
    AiExpertConfig
from gws_ai_toolkit.rag.rag_app._rag_app.rag_app.components.app_config.app_config_state import \
    AppConfigState


class AiExpertConfigState(rx.State):
    """State management for the AI Expert functionality - specialized chat for a specific document."""

    current_form_mode: str = 'full_file'

    async def _get_config(self) -> AiExpertConfig:
        app_config_state = await self.get_state(AppConfigState)
        return await app_config_state.get_config_section('ai_expert_page', AiExpertConfig)

    @rx.var
    async def current_mode(self) -> str:
        """Get the current mode for the AI expert"""
        expert_config = await self._get_config()
        return expert_config.mode

    @rx.var
    async def system_prompt(self) -> str:
        """Get the system prompt for the AI expert"""
        expert_config = await self._get_config()
        return expert_config.system_prompt

    @rx.var
    async def prompt_file_id_placeholder(self) -> str:
        """Get the prompt file ID placeholder for readonly display"""
        expert_config = await self._get_config()
        return expert_config.prompt_file_placeholder

    @rx.event
    async def handle_config_form_submit(self, form_data: dict):
        """Handle the combined configuration form submission (mode and system prompt)"""
        try:
            # Get the new values from form data
            new_mode = form_data.get('mode', '').strip()
            new_system_prompt = form_data.get('system_prompt', '').strip()

            if not new_system_prompt:
                return rx.toast.error("System prompt cannot be empty")

            if not new_mode or new_mode not in ['text_chunk', 'full_file']:
                return rx.toast.error("Invalid mode selected")

            # Get current config
            current_config = await self._get_config()

            if current_config.prompt_file_placeholder not in new_system_prompt:
                return rx.toast.error(
                    f"System prompt must include the prompt file placeholder: {current_config.prompt_file_placeholder}")

            # Create new config with updated values
            new_config = AiExpertConfig(
                prompt_file_placeholder=current_config.prompt_file_placeholder,
                system_prompt=new_system_prompt,
                mode=new_mode
            )

            # Update the config in AppConfigState
            app_config_state = await self.get_state(AppConfigState)
            result = await app_config_state.update_config_section('ai_expert_page', new_config)

            # Show success message
            if result:
                return rx.toast.success("Configuration updated successfully")

            return result

        except (ValueError, KeyError) as e:
            Logger.log_exception_stack_trace(e)
            return rx.toast.error(f"Configuration error: {e}")
        except Exception as e:
            Logger.log_exception_stack_trace(e)
            return rx.toast.error(f"Unexpected error updating configuration: {e}")
