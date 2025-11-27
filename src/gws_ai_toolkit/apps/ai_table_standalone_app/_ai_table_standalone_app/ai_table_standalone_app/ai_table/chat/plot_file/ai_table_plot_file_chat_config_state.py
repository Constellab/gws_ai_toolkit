from typing import cast

import reflex as rx
from gws_ai_toolkit._app.ai_chat import AppConfigState, BaseAnalysisConfig
from gws_core import Logger

from .ai_table_plot_file_chat_config import AiTablePlotFileChatConfig


class AiTablePlotFileChatConfigState(rx.State):
    """State management for AI Table Plot File configuration interface.

    This state class manages the configuration form for AI Table Plot File functionality.
    Unlike the plot_agent version, this configuration has a fixed system prompt that
    cannot be modified by the user, focusing only on model and temperature settings.

    Note:
        The system_prompt is fixed and not configurable for plot_file mode as it
        uses direct file upload to OpenAI with specific analysis capabilities.
    """

    def get_config_section_name(self) -> str:
        """Get the configuration section name for AI Table Plot File

        Returns:
            str: 'ai_table_plot_file_page' configuration section name
        """
        return "ai_table_plot_file_page"

    def get_config_class(self) -> type[BaseAnalysisConfig]:
        """Get the configuration class for AI Table Plot File

        Returns:
            Type[BaseAnalysisConfig]: AiTablePlotFileChatConfig class type
        """
        return AiTablePlotFileChatConfig

    async def get_config(self) -> BaseAnalysisConfig:
        """Get the current configuration for this analysis type"""
        app_config_state = await AppConfigState.get_instance(self)
        config = await app_config_state.get_config_section(self.get_config_section_name(), self.get_config_class())
        return cast(BaseAnalysisConfig, config)

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

    async def handle_config_validation(self, form_data: dict) -> tuple[str, float, str]:
        """Handle configuration form validation for plot_file mode

        Args:
            form_data (dict): Form data from submission

        Returns:
            tuple: (model, temperature, error_message)
                   error_message is empty string if validation passes
        """
        # Get the new values from form data
        new_model = form_data.get("model", "").strip()
        new_temperature_str = form_data.get("temperature", "").strip()

        if not new_model:
            return "", 0.0, "Model cannot be empty"

        # Validate temperature
        try:
            new_temperature = float(new_temperature_str)
            if new_temperature < 0.0 or new_temperature > 2.0:
                return "", 0.0, "Temperature must be between 0.0 and 2.0"
        except ValueError:
            return "", 0.0, "Temperature must be a valid number"

        return new_model, new_temperature, ""

    async def handle_config_save(self, new_config: BaseAnalysisConfig):
        """Save the configuration and show appropriate feedback

        Args:
            new_config (BaseAnalysisConfig): The new configuration to save

        Returns:
            Toast result for user feedback
        """
        try:
            # Update the config in AppConfigState
            app_config_state = await AppConfigState.get_instance(self)
            result = await app_config_state.update_config_section(self.get_config_section_name(), new_config)

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
        """Handle the AI Table Plot File configuration form submission"""
        # Use validation specific to plot_file (no system prompt)
        new_model, new_temperature, error = await self.handle_config_validation(form_data)

        if error:
            return rx.toast.error(error)

        # Get current config to preserve system prompt and placeholder
        current_config = await self.get_config()

        # Create new config with updated values, preserving fixed system prompt
        new_config = AiTablePlotFileChatConfig(
            prompt_file_placeholder=current_config.prompt_file_placeholder,
            system_prompt=current_config.system_prompt,  # Fixed, not configurable
            model=new_model,
            temperature=new_temperature,
        )

        # Save using base class method
        return await self.handle_config_save(new_config)
