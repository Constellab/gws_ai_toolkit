from typing import cast

import reflex as rx
from gws_ai_toolkit._app.ai_chat import AppConfigState

from .ai_table_agent_chat_config import AiTableAgentChatConfig


class AiTableAgentChatConfigState(rx.State):
    """State management for AI Table Agent configuration interface.

    This state class manages the configuration form for AI Table Agent functionality,
    handling user interactions, form validation, and configuration persistence.
    The Table Agent provides unified access to both plotting and transformation
    capabilities through intelligent function calling.

    Key Features:
        - Configuration management for unified table operations
        - Model and temperature settings for optimal function calling
        - Form validation and error handling
        - Configuration persistence across sessions

    Note:
        This configuration allows customization of model and temperature settings
        for optimal performance with function calling and request routing.
    """

    def get_config_section_name(self) -> str:
        """Get the configuration section name for AI Table Agent

        Returns:
            str: 'ai_table_table_agent_page' configuration section name
        """
        return "ai_table_table_agent_page"

    async def get_config(self) -> AiTableAgentChatConfig:
        """Get the current configuration for this analysis type"""
        app_config_state = await AppConfigState.get_instance(self)
        config = await app_config_state.get_config_section(self.get_config_section_name(), AiTableAgentChatConfig)
        return cast(AiTableAgentChatConfig, config)

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

    async def validate_form(self, form_data: dict) -> tuple[str, float, str]:
        """Handle common configuration form validation

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

    async def handle_config_save(self, new_config: AiTableAgentChatConfig):
        """Save the configuration and show appropriate feedback

        Args:
            new_config (AiTableTableAgentChatConfig): The new configuration to save

        Returns:
            Toast result for user feedback
        """
        # Update the config in AppConfigState
        app_config_state = await AppConfigState.get_instance(self)
        return await app_config_state.update_config_section(self.get_config_section_name(), new_config)

    @rx.event
    async def handle_config_form_submit(self, form_data: dict):
        """Handle the AI Table Agent configuration form submission"""
        # Use common validation from base class
        new_model, new_temperature, error = await self.validate_form(form_data)

        if error:
            return rx.toast.error(error)

        # Create new config with updated values
        new_config = AiTableAgentChatConfig(model=new_model, temperature=new_temperature)

        # Save using base class method
        return await self.handle_config_save(new_config)
