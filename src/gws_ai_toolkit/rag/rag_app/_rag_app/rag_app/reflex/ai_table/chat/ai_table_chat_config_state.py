from typing import Type, cast

import reflex as rx
from gws_core import Logger

from ...chat_base.base_analysis_config import BaseAnalysisConfig
from ...core.app_config_state import AppConfigState
from .ai_table_chat_config import AiTableChatConfig


class AiTableChatConfigState(rx.State):
    """State management for AI Table configuration interface.

    This state class manages the configuration form for AI Table functionality,
    handling user interactions, form validation, and configuration persistence.

    Note:
        Unlike AiExpertConfigState, this does not include mode or max_chunks
        configuration as AI Table only operates in full_file mode.
    """

    def get_config_section_name(self) -> str:
        """Get the configuration section name for AI Table

        Returns:
            str: 'ai_table_page' configuration section name
        """
        return 'ai_table_page'

    def get_config_class(self) -> Type[BaseAnalysisConfig]:
        """Get the configuration class for AI Table

        Returns:
            Type[BaseAnalysisConfig]: AiTableConfig class type
        """
        return AiTableChatConfig

    async def get_config(self) -> BaseAnalysisConfig:
        """Get the current configuration for this analysis type"""
        app_config_state = await AppConfigState.get_config_state(self)
        config = await app_config_state.get_config_section(
            self.get_config_section_name(),
            self.get_config_class()
        )
        return cast(BaseAnalysisConfig, config)

    @rx.var
    async def system_prompt(self) -> str:
        """Get the system prompt for the analysis type"""
        config = await self.get_config()
        return config.system_prompt

    @rx.var
    async def prompt_file_id_placeholder(self) -> str:
        """Get the prompt file ID placeholder for readonly display"""
        config = await self.get_config()
        return config.prompt_file_placeholder

    @rx.var
    async def model(self) -> str:
        """Get the model for the analysis type"""
        config = await self.get_config()
        return config.model

    @rx.var
    async def temperature(self) -> float:
        """Get the temperature for the analysis type"""
        config = await self.get_config()
        return config.temperature

    async def handle_common_config_validation(self, form_data: dict) -> tuple[str, str, float, str]:
        """Handle common configuration form validation

        Args:
            form_data (dict): Form data from submission

        Returns:
            tuple: (system_prompt, model, temperature, error_message)
                   error_message is empty string if validation passes
        """
        # Get the new values from form data
        new_system_prompt = form_data.get('system_prompt', '').strip()
        new_model = form_data.get('model', '').strip()
        new_temperature_str = form_data.get('temperature', '').strip()

        if not new_system_prompt:
            return "", "", 0.0, "System prompt cannot be empty"

        if not new_model:
            return "", "", 0.0, "Model cannot be empty"

        # Validate temperature
        try:
            new_temperature = float(new_temperature_str)
            if new_temperature < 0.0 or new_temperature > 2.0:
                return "", "", 0.0, "Temperature must be between 0.0 and 2.0"
        except ValueError:
            return "", "", 0.0, "Temperature must be a valid number"

        # Check placeholder validation
        current_config = await self.get_config()
        if current_config.prompt_file_placeholder not in new_system_prompt:
            return "", "", 0.0, f"System prompt must include the prompt file placeholder: {current_config.prompt_file_placeholder}"

        return new_system_prompt, new_model, new_temperature, ""

    async def handle_config_save(self, new_config: BaseAnalysisConfig):
        """Save the configuration and show appropriate feedback

        Args:
            new_config (BaseAnalysisConfig): The new configuration to save

        Returns:
            Toast result for user feedback
        """
        try:
            # Update the config in AppConfigState
            app_config_state = await AppConfigState.get_config_state(self)
            result = await app_config_state.update_config_section(
                self.get_config_section_name(),
                new_config
            )

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

    @rx.event
    async def handle_config_form_submit(self, form_data: dict):
        """Handle the AI Table configuration form submission"""
        # Use common validation from base class
        new_system_prompt, new_model, new_temperature, error = await self.handle_common_config_validation(form_data)

        if error:
            return rx.toast.error(error)

        # Get current config to preserve placeholder
        current_config = await self.get_config()

        # Create new config with updated values
        new_config = AiTableChatConfig(
            prompt_file_placeholder=current_config.prompt_file_placeholder,
            system_prompt=new_system_prompt,
            model=new_model,
            temperature=new_temperature
        )

        # Save using base class method
        return await self.handle_config_save(new_config)
