import json
from typing import List, Optional

import pandas as pd
import plotly.graph_objects as go
import reflex as rx
from gws_core import BaseModelDTO, File, ResourceModel
from openai.types.responses import (ResponseFunctionCallArgumentsDeltaEvent,
                                    ResponseFunctionCallArgumentsDoneEvent,
                                    ResponseFunctionToolCall,
                                    ResponseOutputItemDoneEvent)
from pydantic import Field

from gws_ai_toolkit._app.chat_base import ChatMessage, OpenAiChatStateBase

from ..ai_table_data_state import ORIGINAL_TABLE_ID, AiTableDataState
from .ai_table_chat_config import AiTableChatConfig
from .ai_table_chat_config_state import AiTableChatConfigState


class PlotlyCodeConfig(BaseModelDTO):
    code: str = Field(
        description="Python code to generate a Plotly figure. The code should use a DataFrame variable named 'df' as input and return a Plotly Figure object.",
    )

    class Config:
        extra = "forbid"  # Prevent additional properties


class AiTableChatState2(OpenAiChatStateBase, rx.State):
    """State management for AI Table Chat - specialized Excel/CSV-focused chat functionality.

    This state class manages the AI Table chat workflow, providing intelligent
    data analysis capabilities focused on a specific Excel or CSV file. It integrates
    with OpenAI's API to provide data analysis, statistical insights, and interactive
    exploration of tabular data using generated Python code execution.

    Key Features:
        - Excel/CSV-specific chat with data analysis capabilities
        - Table metadata sharing (column names, types, row count) instead of file upload
        - OpenAI integration with streaming responses and function calling
        - Dynamic code generation and execution for data visualization
        - Conversation history persistence
        - Error handling and user feedback

    Processing Mode:
        - Metadata-only mode: Shares table structure and metadata with OpenAI
        - Code generation: OpenAI generates Python code for Plotly visualizations
        - Local execution: Generated code is executed locally with the actual DataFrame

    Inherits from BaseFileAnalysisState providing:
        - File loading and validation
        - OpenAI integration with streaming responses
        - Conversation history integration
        - Error handling and user feedback
    """

    # UI configuration
    title = "AI Table Analyst"
    placeholder_text = "Ask about this Excel/CSV data..."
    empty_state_message = "Start analyzing your Excel/CSV data"

    _consecutive_error_count: int = 0

    MAX_CONSECUTIVE_ERRORS = 5  # Max consecutive errors before stopping analysis

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

    async def get_config(self) -> AiTableChatConfig:
        """Get configuration for AI Table analysis

        Returns:
            AiTableChatConfig: Configuration object for AI Table
        """
        app_config_state = await self.get_state(AiTableChatConfigState)
        config = await app_config_state.get_config()
        return config

    def get_analysis_type(self) -> str:
        """Return analysis type for history saving

        Returns:
            str: 'ai_table' identifier
        """
        return "ai_table"

    def _create_custom_prompt(self, table_metadata: str) -> str:
        """Create custom prompt for table analysis with metadata

        Args:
            table_metadata (str): Table metadata including columns, types, and row count
            table_context (str): Context about current table (original or subtable)

        Returns:
            str: Custom prompt for OpenAI
        """
        return f"""You are an AI assistant specialized in data analysis and visualization. You have access to information about a table/dataset but not the actual data.

{table_metadata}

Your role is to help users analyze and visualize this data. When users request visualizations or charts, you should:

1. Generate Python code that creates Plotly figures
2. Use 'df' as the variable name for the DataFrame
3. Ensure the code assigns the final figure to a variable named 'fig'
4. Use appropriate Plotly graph objects (plotly.graph_objects) for visualizations
5. Make reasonable assumptions about data based on column names and types

You can assume the following imports are available:
- pandas as pd
- plotly.graph_objects as go

When generating code, make sure it:
- Uses 'df' as the DataFrame variable
- Creates meaningful visualizations based on the data types
- Handles potential data issues gracefully
- Provide the figure in a variable named 'fig'
- Do not use function definitions
- Do not use return statements

Call the function only once per user request for a chart.

Example code structure:
```python
fig = go.Figure()
# Add traces and configure layout
fig.add_trace(go.Scatter(x=df['column1'], y=df['column2']))
fig.update_layout(title='Chart Title')
```"""

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

    async def get_active_dataframe(self) -> Optional[pd.DataFrame]:
        """Get the active DataFrame for the currently active table (original or subtable)"""
        data_state: AiTableDataState
        async with self:
            data_state = await self.get_state(AiTableDataState)

        dataframe_item = data_state.get_current_dataframe_item()
        if not dataframe_item:
            return None
        return dataframe_item.get_dataframe()

    async def call_ai_chat(self, user_message: str) -> None:
        """Get streaming response from OpenAI about the table data"""

        async with self:
            self._consecutive_error_count = 0
        messages = [{"role": "user", "content": [{"type": "input_text", "text": user_message}]}]
        await self._call_ai_chat(messages)

    async def _call_ai_chat(self, input_messages: List[dict]) -> None:
        """Get streaming response from OpenAI about the table data"""
        client = self._get_openai_client()

        # Get the current dataframe from data state
        config: AiTableChatConfig
        dataframe = await self.get_active_dataframe()

        if dataframe is None:
            raise ValueError("No active dataframe available for analysis")

        async with self:
            config = await self.get_config()

        # Get table metadata
        column_info = []
        for col in dataframe.columns:
            dtype = str(dataframe[col].dtype)
            column_info.append(f"{col}: {dtype}")

        table_metadata = f"""Table Information:
- Columns ({len(dataframe.columns)}): {', '.join(column_info)}
- Number of rows: {len(dataframe)}
- Table shape: {dataframe.shape}"""

        instructions = self._create_custom_prompt(table_metadata)

        tools = [
            {"type": "function",
             "name": "generate_plotly_figure",
             "description":
             "Generate Python code that creates a Plotly figure. The code should use 'df' as the DataFrame variable and return a Plotly Figure object.",
             "parameters": PlotlyCodeConfig.model_json_schema()}]

        with client.responses.stream(
            model=config.model,
            instructions=instructions,
            input=input_messages,
            temperature=config.temperature,
            previous_response_id=self._previous_external_response_id,
            tools=tools
        ) as stream:

            # Process streaming events
            for event in stream:
                # print("Received event:", event.type, type(event), type(event.item) if hasattr(event, 'item') else None)
                # Route events to specific handler methods
                if event.type == "response.output_text.delta":
                    await self.handle_output_text_delta(event)
                elif event.type == "response.code_interpreter_call_code.delta":
                    await self.handle_code_interpreter_call_code_delta(event)
                elif event.type == "response.function_call_arguments.delta":
                    await self.handle_function_call_arguments_delta(event)
                # elif event.type == "response.function_call_arguments.done":
                #     await self.handle_function_call_arguments_done(event)
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

        if not isinstance(event.item, ResponseFunctionToolCall):
            return

        try:
            await self._execute_generated_code(event.item.arguments)
        except Exception as exec_error:
            await self._handle_function_error(event.item.call_id, str(exec_error), event.item.to_dict())

            return

        # Mark the function as successful if it was a function call
        await self._mark_function_call_as_successful(event.item.call_id, event.item.to_dict())

    async def _mark_function_call_as_successful(self, call_id: str, item: dict) -> None:
        """Mark a function call as successful in the current response"""
        if not self._current_external_response_id:
            return

        await self._call_ai_chat([item,
                                  {
                                      "type": "function_call_output",
                                      "call_id": call_id,
                                      "output": json.dumps({
                                          "Plot": "Successfully created the chart."
                                      })
                                  }])

    async def _handle_function_error(self, call_id: str, error_message: str, item: dict) -> None:
        error_chat_message = await self.create_error_message(error_message)
        await self.update_current_response_message(error_chat_message)

        async with self:
            self._consecutive_error_count += 1

        messages = [item, {
            "type": "function_call_output",
                    "call_id": call_id,
                    "output": json.dumps({
                        "Error": error_message
                    })
        }]

        if self._consecutive_error_count >= self.MAX_CONSECUTIVE_ERRORS:
            # If too many consecutive errors, stop further analysis
            stop_message = await self.create_error_message(
                "Too many consecutive errors occurred during analysis. Please update your query.")
            await self.update_current_response_message(stop_message)

            messages.append({"role": "user", "content": [{"type": "input_text", "text": "Stop further analysis."}]})
        else:
            # If execution failed, we do not mark the function as successful
            messages.append({"role": "user", "content": [{"type": "input_text", "text": "Can you fix the code?"}]})

        await self._call_ai_chat(messages)

    async def handle_function_call_arguments_delta(self, event: ResponseFunctionCallArgumentsDeltaEvent):
        """Handle response.function_call_arguments.delta event"""
        # This would handle streaming function arguments, but typically we wait for the complete arguments
        # Implementation can be added here if streaming function arguments is needed

    async def handle_function_call_arguments_done(self, event: ResponseFunctionCallArgumentsDoneEvent):
        """Handle response.function_call_arguments.done event - execute the generated code"""

        arguments_str = event.arguments
        await self._execute_generated_code(arguments_str)

    async def _execute_generated_code(self, arguments_str: str) -> None:

        # Since we only have one function defined, we can assume it's generate_plotly_figure
        # Parse arguments
        arguments = json.loads(arguments_str)
        code = arguments.get('code', '')

        if not code:
            raise ValueError("No code provided in function arguments")

        # Load the current dataframe for code execution
        df = await self.get_active_dataframe()

        # Execute the generated code
        # Create a safe execution environment with the dataframe
        execution_globals = {
            'df': df,
            'pd': pd,
            'go': go,
            '__builtins__': __builtins__
        }

        # Execute the code and capture the result
        try:
            exec(code, execution_globals)
        except Exception as exec_error:
            raise RuntimeError(f"Error executing generated code: {exec_error}")

        # The code should have created a 'fig' variable or returned a figure
        # Look for common variable names that might contain the figure
        if 'fig' not in execution_globals:
            # If 'fig' is not defined, check if the code returned a figure directly
            raise Exception(
                "The executed code did not define a variable named 'fig'. Make sure to assign the plotly figure to a variable named 'fig'.")

        fig = execution_globals['fig']

        # If fig is not a plotly figure, raise an error
        if not isinstance(fig, go.Figure):
            raise Exception(
                "The 'fig' variable is not a Plotly figure. Make sure to assign a plotly `Figure` object to a variable named 'fig'.")

        # Create a success message showing the chart has been created
        success_message: ChatMessage
        async with self:
            success_message = await self.create_plotly_message(
                figure=fig,
                role="assistant",
                external_id=self._current_external_response_id
            )
        await self.update_current_response_message(success_message)

    async def close_current_message(self):
        """Close the current streaming message and add it to the chat history, then save to conversation history."""
        if not self._current_response_message:
            return
        await super().close_current_message()
        # Save conversation after message is added to history
        await self._save_conversation_to_history()

    async def _save_conversation_to_history(self):
        """Save current conversation to history with analysis-specific configuration."""
        config: AiTableChatConfig
        async with self:
            config = await self.get_config()

        # Save conversation to history after response is completed
        await self.save_conversation_to_history(self.get_analysis_type(), config.to_json_dict())
