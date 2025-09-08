from typing import Optional

import reflex as rx
from gws_core import File, ResourceModel

from ..chat_base.base_file_analysis_state import BaseFileAnalysisState
from .ai_table_config import AiTableConfig
from .ai_table_config_state import AiTableConfigState


class AiTableChatState(BaseFileAnalysisState, rx.State):
    """State management for AI Table Chat - specialized Excel/CSV-focused chat functionality.

    This state class manages the AI Table chat workflow, providing intelligent
    data analysis capabilities focused on a specific Excel or CSV file. It integrates
    with OpenAI's API to provide data analysis, statistical insights, and interactive
    exploration of tabular data using code interpreter with pandas.

    Key Features:
        - Excel/CSV-specific chat with full data analysis capabilities
        - Full file upload to OpenAI with code interpreter access
        - OpenAI integration with streaming responses
        - Data visualization and statistical analysis
        - Conversation history persistence
        - Error handling and user feedback

    Processing Mode:
        - Only supports full_file mode: Uploads entire Excel/CSV file to OpenAI
          with code interpreter access for comprehensive data analysis

    Inherits from BaseFileAnalysisState providing:
        - File loading and validation
        - OpenAI integration with streaming responses
        - File upload to OpenAI with code interpreter access
        - Conversation history integration
        - Error handling and user feedback
    """

    # UI configuration
    title = "AI Table Analyst"
    placeholder_text = "Ask about this Excel/CSV data..."
    empty_state_message = "Start analyzing your Excel/CSV data"

    def set_resource(self, resource: ResourceModel):
        """Set the resource to analyze and validate it's an Excel/CSV file

        Args:
            resource (ResourceModel): Resource model to set
        """
        self.clear_chat()
        self._current_resource_model = resource

    def validate_resource(self, resource: ResourceModel) -> bool:
        """Validate if file is an Excel or CSV file

        Args:
            resource (ResourceModel): Resource to validate

        Returns:
            bool: True if file is Excel/CSV, False otherwise
        """
        file = resource.get_resource()

        if not isinstance(file, File):
            return False
        return file.is_csv_or_excel()

    async def get_config(self) -> AiTableConfig:
        """Get configuration for AI Table analysis

        Returns:
            AiTableConfig: Configuration object for AI Table
        """
        app_config_state = await self.get_state(AiTableConfigState)
        return await app_config_state.get_config()

    def get_analysis_type(self) -> str:
        """Return analysis type for history saving

        Returns:
            str: 'ai_table' identifier
        """
        return "ai_table"

    def _load_resource_from_id(self) -> Optional[ResourceModel]:
        # try to load from rag document id
        # Get the dynamic route parameter - different subclasses may use different parameter names
        resource_id = self.resource_id if hasattr(self, 'resource_id') else None

        if not resource_id:
            return None

        resource_model = ResourceModel.get_by_id(resource_id)
        if not resource_model:
            raise ValueError(f"Resource with id {resource_id} not found")

        return resource_model

    async def call_ai_chat(self, user_message: str):
        """Get streaming response from OpenAI about the file"""
        client = self._get_openai_client()

        # Get the current dataframe from data state
        config: AiTableConfig
        async with self:
            config = await self.get_config()

        # Upload file and use code interpreter
        uploaded_file_id = await self.upload_file_to_openai()
        system_prompt = config.system_prompt.replace(
            config.prompt_file_placeholder, uploaded_file_id)

        instructions = system_prompt
        tools = [{"type": "code_interpreter", "container": {"type": "auto", "file_ids": [uploaded_file_id]}}]

        # Create streaming response with code interpreter
        with client.responses.stream(
            model=config.model,
            instructions=instructions,
            input=[{"role": "user", "content": [{"type": "input_text", "text": user_message}]}],
            temperature=config.temperature,
            previous_response_id=self.conversation_id,
            tools=tools,
        ) as stream:

            # Process streaming events
            for event in stream:
                # Route events to specific handler methods
                if event.type == "response.output_text.delta":
                    await self.handle_output_text_delta(event)
                elif event.type == "response.code_interpreter_call_code.delta":
                    await self.handle_code_interpreter_call_code_delta(event)
                elif event.type == "response.output_text_annotation.added":
                    await self.handle_output_text_annotation_added(event)
                elif event.type == "response.output_item.added":
                    await self.close_current_message()
                elif event.type == "response.output_item.done":
                    await self.close_current_message()
                elif event.type == "response.created":
                    # Save the response ID for future conversation continuity
                    if hasattr(event, 'response') and hasattr(event.response, 'id'):
                        async with self:
                            self.conversation_id = event.response.id

            # Get the final response to extract response ID if not already captured
            final_response = stream.get_final_response()
            if final_response and hasattr(final_response, 'id') and not self.conversation_id:
                async with self:
                    self.set_conversation_id(final_response.id)

    def _after_chat_cleared(self):
        """Reset any analysis-specific state after chat is cleared."""
        # No additional state to reset for AI Table chat currently
        pass
