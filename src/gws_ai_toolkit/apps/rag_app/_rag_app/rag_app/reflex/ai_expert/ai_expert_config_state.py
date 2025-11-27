from typing import cast

import reflex as rx
from gws_core import Logger

from ..core.app_config_state import AppConfigState
from .ai_expert_config import AiExpertChatMode, AiExpertConfig


class AiExpertConfigState(rx.State):
    """State management for AI Expert configuration interface.

    This state class manages the configuration form for AI Expert functionality,
    handling user interactions, form validation, and configuration persistence.
    It provides a bridge between the UI configuration form and the application's
    configuration system.

    The state manages:
        - Form field values and validation
        - Dynamic field visibility based on mode selection
        - Configuration loading from and saving to the application config
        - Form submission handling with error management
        - Real-time updates for reactive form elements

    Key Features:
        - Async configuration loading and saving
        - Form validation with user-friendly error messages
        - Dynamic form behavior (fields show/hide based on selections)
        - Integration with AppConfigState for persistence
        - Toast notifications for user feedback

    Attributes:
        current_form_mode (AiExpertChatMode): Currently selected mode in the form,
            used for dynamic field visibility and validation.
    """

    current_form_mode: AiExpertChatMode = 'full_file'

    async def get_config(self) -> AiExpertConfig:
        app_config_state = await AppConfigState.get_instance(self)
        config = await app_config_state.get_config_section('ai_expert_page', AiExpertConfig)
        return cast(AiExpertConfig, config)

    @rx.var
    async def current_mode(self) -> str:
        """Get the current mode for the AI expert"""
        expert_config = await self.get_config()
        return expert_config.mode

    @rx.var
    async def system_prompt(self) -> str:
        """Get the system prompt for the AI expert"""
        expert_config = await self.get_config()
        return expert_config.system_prompt

    @rx.var
    async def prompt_file_id_placeholder(self) -> str:
        """Get the prompt file ID placeholder for readonly display"""
        expert_config = await self.get_config()
        return expert_config.prompt_file_placeholder

    @rx.var
    async def model(self) -> str:
        """Get the model for the AI expert"""
        expert_config = await self.get_config()
        return expert_config.model

    @rx.var
    async def temperature(self) -> float:
        """Get the temperature for the AI expert"""
        expert_config = await self.get_config()
        return expert_config.temperature

    @rx.var
    async def max_chunks(self) -> int:
        """Get the max chunks for the AI expert"""
        expert_config = await self.get_config()
        return expert_config.max_chunks

    @rx.event
    async def handle_config_form_submit(self, form_data: dict):
        """Handle the combined configuration form submission (mode, system prompt, model, and temperature)"""
        try:
            # Get the new values from form data
            new_mode = form_data.get('mode', '').strip()
            new_system_prompt = form_data.get('system_prompt', '').strip()
            new_model = form_data.get('model', '').strip()
            new_temperature_str = form_data.get('temperature', '').strip()
            new_max_chunks_str = form_data.get('max_chunks', '').strip()

            if not new_system_prompt:
                return rx.toast.error("System prompt cannot be empty")

            if not new_mode or new_mode not in ['full_text_chunk', 'relevant_chunks', 'full_file']:
                return rx.toast.error("Invalid mode selected")

            if not new_model:
                return rx.toast.error("Model cannot be empty")

            # Validate temperature
            try:
                new_temperature = float(new_temperature_str)
                if new_temperature < 0.0 or new_temperature > 2.0:
                    return rx.toast.error("Temperature must be between 0.0 and 2.0")
            except ValueError:
                return rx.toast.error("Temperature must be a valid number")

            # Validate max_chunks (only required for relevant_chunks mode)
            new_max_chunks = 5  # default value
            if new_mode == 'relevant_chunks':
                if not new_max_chunks_str:
                    return rx.toast.error("Chunk count is required for relevant chunks mode")
                try:
                    new_max_chunks = int(new_max_chunks_str)
                    if new_max_chunks < 1 or new_max_chunks > 100:
                        return rx.toast.error("Chunk count must be between 1 and 100")
                except ValueError:
                    return rx.toast.error("Chunk count must be a valid number")
            elif new_max_chunks_str:
                # If max_chunks is provided for other modes, validate it but use it
                try:
                    new_max_chunks = int(new_max_chunks_str)
                    if new_max_chunks < 1 or new_max_chunks > 100:
                        return rx.toast.error("Chunk count must be between 1 and 100")
                except ValueError:
                    return rx.toast.error("Chunk count must be a valid number")

            # Get current config
            current_config = await self.get_config()

            if current_config.prompt_file_placeholder not in new_system_prompt:
                return rx.toast.error(
                    f"System prompt must include the prompt file placeholder: {current_config.prompt_file_placeholder}")

            # Create new config with updated values
            new_config = AiExpertConfig(
                prompt_file_placeholder=current_config.prompt_file_placeholder,
                system_prompt=new_system_prompt,
                mode=new_mode,
                model=new_model,
                temperature=new_temperature,
                max_chunks=new_max_chunks
            )

            # Update the config in AppConfigState

            app_config_state = await AppConfigState.get_instance(self)
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

    async def on_form_mount(self):
        self.current_form_mode = await self.current_mode

    def on_mode_change(self, new_mode: AiExpertChatMode):
        self.current_form_mode = new_mode

    @rx.var
    def show_max_chunk_config(self) -> bool:
        return self.current_form_mode == "relevant_chunks" or self.current_form_mode == "full_text_chunk"
