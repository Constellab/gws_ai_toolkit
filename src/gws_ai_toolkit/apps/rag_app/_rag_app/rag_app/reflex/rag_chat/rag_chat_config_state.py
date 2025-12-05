from typing import cast

import reflex as rx
from gws_ai_toolkit.models.chat.conversation.rag_chat_config import RagChatConfig
from gws_core import Logger

from ..core.app_config_state import AppConfigState


class RagChatConfigState(rx.State):
    """State management for RAG Chat configuration interface.

    This state class manages the configuration form for RAG Chat functionality,
    handling user interactions, form validation, and configuration persistence.
    It provides a bridge between the UI configuration form and the application's
    configuration system.

    The state manages:
        - Form field values and validation
        - Configuration loading from and saving to the application config
        - Form submission handling with error management
        - Real-time updates for reactive form elements

    Key Features:
        - Async configuration loading and saving
        - Form validation with user-friendly error messages
        - Integration with AppConfigState for persistence
        - Toast notifications for user feedback

    Attributes:
        None - All configuration is loaded from AppConfigState
    """

    async def get_config(self) -> RagChatConfig:
        app_config_state = await AppConfigState.get_instance(self)
        config = await app_config_state.get_config_section("rag_chat_page", RagChatConfig)
        return cast(RagChatConfig, config)

    @rx.var
    async def placeholder_text(self) -> str:
        """Get the placeholder text for the RAG chat"""
        chat_config = await self.get_config()
        return chat_config.placeholder_text

    @rx.event
    async def handle_config_form_submit(self, form_data: dict):
        """Handle the configuration form submission (placeholder text)"""
        try:
            # Get the new value from form data
            new_placeholder_text = form_data.get("placeholder_text", "").strip()

            if not new_placeholder_text:
                return rx.toast.error("Placeholder text cannot be empty")

            # Create new config with updated value
            new_config = RagChatConfig(
                placeholder_text=new_placeholder_text,
            )

            # Update the config in AppConfigState
            app_config_state = await AppConfigState.get_instance(self)
            result = await app_config_state.update_config_section("rag_chat_page", new_config)

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
