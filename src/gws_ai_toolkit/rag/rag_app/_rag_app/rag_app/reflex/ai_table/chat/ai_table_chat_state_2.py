import json
from typing import Optional

import pandas as pd
import plotly.graph_objects as go
import reflex as rx
from gws_core import BaseModelDTO, File, Logger, ResourceModel
from openai.types.responses import (ResponseFunctionCallArgumentsDeltaEvent,
                                    ResponseFunctionCallArgumentsDoneEvent,
                                    ResponseOutputItemDoneEvent)
from pydantic import Field

from ...chat_base.base_file_analysis_state import BaseFileAnalysisState
from ...chat_base.chat_message_class import ChatMessage
from ..ai_table_data_state import ORIGINAL_TABLE_ID, AiTableDataState
from .ai_table_chat_config import AiTableChatConfig
from .ai_table_chat_config_state import AiTableChatConfigState


class PlotlyCodeConfig(BaseModelDTO):
    code: str = Field(
        description="Python code to generate a Plotly figure. The code should use a DataFrame variable named 'df' as input and return a Plotly Figure object.",
    )

    class Config:
        extra = "forbid"  # Prevent additional properties


class AiTableChatState2(BaseFileAnalysisState, rx.State):
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

    def _create_custom_prompt(self, table_metadata: str, table_context: str) -> str:
        """Create custom prompt for table analysis with metadata

        Args:
            table_metadata (str): Table metadata including columns, types, and row count
            table_context (str): Context about current table (original or subtable)

        Returns:
            str: Custom prompt for OpenAI
        """
        return f"""You are an AI assistant specialized in data analysis and visualization. You have access to information about a table/dataset but not the actual data.

{table_metadata}

{table_context}

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

    async def call_ai_chat(self, user_message: str):
        """Get streaming response from OpenAI about the table data"""
        client = self._get_openai_client()

        # Get the current dataframe from data state
        config: AiTableChatConfig
        data_state: AiTableDataState
        async with self:
            config = await self.get_config()
            data_state = await self.get_state(AiTableDataState)

        # Get active table metadata instead of uploading file
        active_file_path = await self.get_active_file_path()
        if not active_file_path:
            raise ValueError("No active file available for analysis")

        # Load dataframe to get metadata
        try:
            if active_file_path.endswith('.csv'):
                df = pd.read_csv(active_file_path)
            else:
                df = pd.read_excel(active_file_path)

            # Get table metadata
            column_info = []
            for col in df.columns:
                dtype = str(df[col].dtype)
                column_info.append(f"{col}: {dtype}")

            table_metadata = f"""Table Information:
- Columns ({len(df.columns)}): {', '.join(column_info)}
- Number of rows: {len(df)}
- Table shape: {df.shape}"""

        except Exception as e:
            table_metadata = f"Error loading table metadata: {str(e)}"

        # Create custom prompt with table metadata
        table_context = ""
        if data_state.current_table_id != ORIGINAL_TABLE_ID:
            table_context = f"Currently analyzing subtable: {data_state.current_table_name}"
        else:
            table_context = f"Currently analyzing original table: {data_state.current_table_name}"

        instructions = self._create_custom_prompt(table_metadata, table_context)

        tools = [
            {"type": "function",
             "name": "generate_plotly_figure",
             "description":
             "Generate Python code that creates a Plotly figure. The code should use 'df' as the DataFrame variable and return a Plotly Figure object.",
             "parameters": PlotlyCodeConfig.model_json_schema()}]

        with client.responses.stream(
            model=config.model,
            instructions=instructions,
            input=[{"role": "user", "content": [{"type": "input_text", "text": user_message}]}],
            temperature=config.temperature,
            previous_response_id=self._previous_external_response_id,
            tools=tools
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
            config: AiTableChatConfig
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
        # Implementation can be added here if streaming function arguments is needed

    async def handle_function_call_arguments_done(self, event: ResponseFunctionCallArgumentsDoneEvent):
        """Handle response.function_call_arguments.done event - execute the generated code"""

        arguments_str = event.arguments

        # Since we only have one function defined, we can assume it's generate_plotly_figure
        try:
            # Parse arguments
            arguments = json.loads(arguments_str)
            code = arguments.get('code', '')

            if not code:
                raise ValueError("No code provided in function arguments")

            # Load the current dataframe for code execution
            active_file_path = await self.get_active_file_path()
            if not active_file_path:
                raise ValueError("No active file available for analysis")

            # Load dataframe
            if active_file_path.endswith('.csv'):
                df = pd.read_csv(active_file_path)
            else:
                df = pd.read_excel(active_file_path)

            # Execute the generated code
            # Create a safe execution environment with the dataframe
            execution_globals = {
                'df': df,
                'pd': pd,
                'go': go,
                '__builtins__': __builtins__
            }

            # Execute the code and capture the result
            exec(code, execution_globals)

            # The code should have created a 'fig' variable or returned a figure
            # Look for common variable names that might contain the figure
            fig = None
            for var_name in ['fig', 'figure', 'plot']:
                if var_name in execution_globals and hasattr(execution_globals[var_name], 'to_dict'):
                    fig = execution_globals[var_name]
                    break

            if fig is None:
                raise ValueError(
                    "The executed code did not produce a Plotly figure. Make sure to assign the figure to a variable named 'fig'.")

            # Create a success message showing the chart has been created
            success_message: ChatMessage
            async with self:
                success_message = await self.create_plotly_message(
                    figure=fig,
                    role="assistant",
                    external_id=self._current_external_response_id
                )
            await self.update_current_response_message(success_message)

        except Exception as e:
            Logger.log_exception_stack_trace(e)
            error_message = self.create_text_message(
                content=f"❌ Error executing generated code: {str(e)}",
                role="assistant",
                external_id=self._current_external_response_id
            )
            await self.update_current_response_message(error_message)
