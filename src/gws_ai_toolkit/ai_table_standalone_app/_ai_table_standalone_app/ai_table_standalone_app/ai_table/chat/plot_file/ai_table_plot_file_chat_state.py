import json
from typing import Optional

import plotly.graph_objects as go
import reflex as rx
from gws_core import BaseModelDTO, File, Logger, ResourceModel
from openai.types.responses import (ResponseFunctionCallArgumentsDeltaEvent,
                                    ResponseFunctionCallArgumentsDoneEvent,
                                    ResponseOutputItemDoneEvent)
from pydantic import Field

from gws_ai_toolkit._app.chat_base import BaseFileAnalysisState, ChatMessage

from ...ai_table_data_state import ORIGINAL_TABLE_ID, AiTableDataState
from .ai_table_plot_file_chat_config import AiTablePlotFileChatConfig
from .ai_table_plot_file_chat_config_state import AiTablePlotFileChatConfigState


class PlotlyFigureConfig(BaseModelDTO):
    fig_config: dict = Field(
        description="Plotly figure configuration as dictionary - result of plotly fig.to_dict()",
    )

    class Config:
        extra = "forbid"  # Prevent additional properties


class AiTablePlotFileChatState(BaseFileAnalysisState, rx.State):
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

    previous_response_id: Optional[str] = None  # For conversation continuity

    # UI configuration
    title = "AI Table Analyst"
    placeholder_text = "Ask about this Excel/CSV data..."
    empty_state_message = "Start analyzing your Excel/CSV data"

    def set_resource(self, resource: ResourceModel):
        """Set the resource to analyze and validate it's an Excel/CSV file

        Args:
            resource (ResourceModel): Resource model to set
        """
        if self._current_resource_model and self._current_resource_model.id == resource.id:
            return  # No change
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

    async def get_config(self) -> AiTablePlotFileChatConfig:
        """Get configuration for AI Table analysis

        Returns:
            AiTableConfig: Configuration object for AI Table
        """
        app_config_state = await self.get_state(AiTablePlotFileChatConfigState)
        config = await app_config_state.get_config()
        return config

    def get_analysis_type(self) -> str:
        """Return analysis type for history saving

        Returns:
            str: 'ai_table' identifier
        """
        return "ai_table"

    def _load_resource(self) -> Optional[ResourceModel]:
        # try to load from rag document id
        # Get the dynamic route parameter - different subclasses may use different parameter names
        resource_id = self.resource_id if hasattr(self, 'resource_id') else None

        if not resource_id:
            return None

        resource_model = ResourceModel.get_by_id(resource_id)
        if not resource_model:
            raise ValueError(f"Resource with id {resource_id} not found")

        return resource_model

    async def get_active_file_path(self) -> Optional[str]:
        """Get the file path for the currently active table (original or subtable)"""
        data_state: AiTableDataState
        async with self:
            data_state = await self.get_state(AiTableDataState)

        # If a subtable is active, use its file path
        if data_state.current_table_id != ORIGINAL_TABLE_ID:
            table_item = data_state._get_table_dataframe_item_by_id(data_state.current_table_id)
            if table_item:
                return table_item.file_path

        # Otherwise use original file
        if data_state.current_file_path:
            return data_state.current_file_path

        return None

    async def upload_active_file_to_openai(self, file_path: str) -> str:
        """Upload the active file (original or subtable) to OpenAI and return file ID"""
        client = self._get_openai_client()

        # Upload file to OpenAI
        with open(file_path, "rb") as f:
            uploaded_file = client.files.create(
                file=f,
                purpose='assistants'
            )

        # Cache the file ID (note: for subtables, we don't cache since they're temporary)
        file_id = uploaded_file.id

        return file_id

    async def call_ai_chat(self, user_message: str):
        """Get streaming response from OpenAI about the file"""
        client = self._get_openai_client()

        # Get the current dataframe from data state
        config: AiTablePlotFileChatConfig
        data_state: AiTableDataState
        async with self:
            config = await self.get_config()
            data_state = await self.get_state(AiTableDataState)

        # Get active file path (original or subtable)
        active_file_path = await self.get_active_file_path()
        if not active_file_path:
            raise ValueError("No active file available for analysis")

        # Upload the active file and use code interpreter
        uploaded_file_id = await self.upload_active_file_to_openai(active_file_path)

        # Update system prompt with context about current table
        table_context = ""
        if data_state.current_table_id != ORIGINAL_TABLE_ID:
            table_context = f" (Currently analyzing subtable: {data_state.current_table_name})"
        else:
            table_context = f" (Currently analyzing original table: {data_state.current_table_name})"

        system_prompt = config.system_prompt.replace(
            config.prompt_file_placeholder, uploaded_file_id) + table_context

        instructions = system_prompt

        tools = [
            {"type": "code_interpreter", "container": {"type": "auto", "file_ids": [uploaded_file_id]}},
            {
                "type": "function",
                # "strict": True,
                "name": "create_plotly_figure",
                "description": "Create a Plotly figure from JSON configuration. Use this when you want to create interactive charts and visualizations.",
                "parameters": PlotlyFigureConfig.model_json_schema()

            },
        ]

        # Create streaming response with code interpreter and function calling
        with client.responses.stream(
            model=config.model,
            instructions=instructions,
            input=[{"role": "user", "content": [{"type": "input_text", "text": user_message}]}],
            temperature=config.temperature,
            previous_response_id=self._previous_external_response_id,
            tools=tools,
        ) as stream:

            # Process streaming events
            for event in stream:
                # Route events to specific handler methods
                if event.type == "response.output_text.delta":
                    await self.handle_output_text_delta(event)
                elif event.type == "response.code_interpreter_call_code.delta":
                    await self.handle_code_interpreter_call_code_delta(event)
                elif event.type == "response.output_text.annotation.added":
                    await self.handle_output_text_annotation_added(event)
                elif event.type == "response.function_call_arguments.delta":
                    await self.handle_function_call_arguments_delta(event)
                elif event.type == "response.function_call_arguments.done":
                    await self.handle_function_call_arguments_done(event)
                elif event.type == "response.output_item.added":
                    await self.close_current_message()
                elif event.type == "response.output_item.done":
                    await self.handle_output_item_done(event)
                elif event.type == "response.created":
                    await self.handle_response_created(event)
                elif event.type == "response.completed":
                    await self.handle_response_completed()

    async def handle_output_item_done(self, event: ResponseOutputItemDoneEvent):
        """Handle response.output_item.done event - close current message"""
        await self.close_current_message()

        # Mark the function as successful if it was a function call
        if event.item.call_id:
            # Get the current dataframe from data state
            config: AiTablePlotFileChatConfig
            async with self:
                config = await self.get_config()

            input_list = []
            input_list.append({
                "type": "function_call_output",
                "call_id": event.item.call_id,
                "output": json.dumps({
                    "Plot": "Successfully created the chart."
                })
            })

            client = self._get_openai_client()

            response = client.responses.create(
                model=config.model,
                instructions="Tool response.",
                input=input_list,
                previous_response_id=self._current_external_response_id,
            )

            async with self:
                self._current_external_response_id = response.id

    async def handle_function_call_arguments_delta(self, event: ResponseFunctionCallArgumentsDeltaEvent):
        """Handle response.function_call_arguments.delta event"""
        # This would handle streaming function arguments, but typically we wait for the complete arguments
        pass

    async def handle_function_call_arguments_done(self, event: ResponseFunctionCallArgumentsDoneEvent):
        """Handle response.function_call_arguments.done event - execute the function call"""

        arguments_str = event.arguments

        # Since we only have one function defined, we can assume it's create_plotly_figure
        # In a more complex setup, we'd need to track the function name from earlier events
        try:
            # Parse arguments
            arguments = json.loads(arguments_str)

            # Create Plotly figure from config - this is what the user requested
            fig = go.Figure(arguments)

            # Create a success message showing the chart has been created
            success_message: ChatMessage
            async with self:
                success_message = await self.create_plotly_message(
                    figure=fig,
                    role="assistant",
                    external_id=self._current_external_response_id
                )
            await self.update_current_response_message(success_message)

        except json.JSONDecodeError as e:
            Logger.log_exception_stack_trace(e)
            error_message = self.create_text_message(
                content=f"❌ Error parsing function arguments: {str(e)}",
                role="assistant",
                external_id=self._current_external_response_id
            )
            await self.update_current_response_message(error_message)
        except Exception as e:
            Logger.log_exception_stack_trace(e)
            error_message = self.create_text_message(
                content=f"❌ Error creating Plotly figure: {str(e)}",
                role="assistant",
                external_id=self._current_external_response_id
            )
            await self.update_current_response_message(error_message)
