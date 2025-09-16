import json
from typing import Generator, List, Optional

import pandas as pd
import plotly.graph_objects as go
from gws_core import BaseModelDTO
from openai import OpenAI
from openai.types.responses import (ResponseFunctionToolCall,
                                    ResponseOutputItemDoneEvent)
from pydantic import Field

from .plotly_agent_ai_events import (
    PlotAgentEvent, TextDeltaEvent, PlotGeneratedEvent,
    ErrorEvent, ResponseCreatedEvent, ResponseCompletedEvent,
    OutputItemAddedEvent, OutputItemDoneEvent
)


class PlotlyCodeConfig(BaseModelDTO):
    """Configuration for Plotly code generation"""
    code: str = Field(
        description="Python code to generate a Plotly figure. The code should use a DataFrame variable named 'df' as input and return a Plotly Figure object.",
    )

    class Config:
        extra = "forbid"  # Prevent additional properties


class PlotyAgentAi:
    """Standalone plot agent service for data visualization using OpenAI"""

    MAX_CONSECUTIVE_ERRORS = 5

    _openai_client: OpenAI
    _consecutive_error_count: int
    _dataframe: pd.DataFrame
    _model: str
    _temperature: float

    def __init__(self, openai_client: OpenAI,
                 dataframe: pd.DataFrame,
                 model: str,
                 temperature: float):
        self._openai_client = openai_client
        self._consecutive_error_count = 0
        self._dataframe = dataframe
        self._model = model
        self._temperature = temperature

    def generate_plot_stream(
        self,
        user_query: str,
        previous_response_id: Optional[str] = None
    ) -> Generator[PlotAgentEvent, None, None]:
        """Generate plot with streaming events

        Args:
            user_query: User's request for visualization
            previous_response_id: Previous OpenAI response ID for conversation continuity

        Yields:
            PlotAgentEvent: Stream of events during plot generation
        """
        self._consecutive_error_count = 0

        # Prepare messages and prompt
        messages = [{"role": "user", "content": [{"type": "input_text", "text": user_query}]}]
        for event in self._generate_plot_stream_internal(messages, previous_response_id):
            yield event

    def _generate_plot_stream_internal(
        self,
        input_messages: List[dict],
        previous_response_id: Optional[str] = None
    ) -> Generator[PlotAgentEvent, None, None]:
        """Internal method for plot generation with streaming"""

        # Create prompt with table metadata
        table_metadata = self._get_table_metadata()
        prompt = self._create_plot_prompt(table_metadata)

        # Define tools for OpenAI
        tools = [
            {"type": "function", "name": "generate_plotly_figure",
             "description":
             "Generate Python code that creates a Plotly figure. The code should use 'df' as the DataFrame variable and return a Plotly Figure object.",
             "parameters": PlotlyCodeConfig.model_json_schema()}]

        current_response_id = None

        # Stream OpenAI response directly
        with self._openai_client.responses.stream(
            model=self._model,
            instructions=prompt,
            input=input_messages,
            temperature=self._temperature,
            previous_response_id=previous_response_id,
            tools=tools
        ) as stream:

            # Process streaming events
            for event in stream:
                # Yield streaming events to consumer
                if event.type == "response.output_text.delta":
                    yield TextDeltaEvent(delta=event.delta)
                elif event.type == "response.output_item.added":
                    yield OutputItemAddedEvent(
                        item_data=event.to_dict() if hasattr(event, 'to_dict') else str(event)
                    )
                elif event.type == "response.created":
                    current_response_id = event.response.id if hasattr(event, 'response') else None
                    yield ResponseCreatedEvent(response_id=current_response_id)
                elif event.type == "response.completed":
                    yield ResponseCompletedEvent()
                elif event.type == "response.output_item.done":
                    yield OutputItemDoneEvent(item_data=event)
                    for item_event in self._handle_output_item_done(event, current_response_id):
                        yield item_event

    def _handle_output_item_done(self, event: ResponseOutputItemDoneEvent,
                                 current_response_id: Optional[str]) -> Generator[PlotAgentEvent, None, None]:
        """Handle output item done event"""
        # Handle function call completion
        if self._is_function_call_event(event):
            function_args = self._parse_function_arguments(event)
            call_id = self._get_function_call_id(event)

            if function_args:
                try:
                    figure, code = self._execute_generated_code(function_args)

                    yield PlotGeneratedEvent(
                        figure=figure,
                        code=code,
                        call_id=call_id,
                        response_id=current_response_id
                    )

                    # For now, just return after successful plot generation
                    # TODO: In the future, we might want to continue the conversation
                    return

                except Exception as exec_error:
                    self._consecutive_error_count += 1

                    yield ErrorEvent(
                        message=str(exec_error),
                        code=None,
                        error_type="execution_error",
                        consecutive_error_count=self._consecutive_error_count,
                        is_recoverable=self._consecutive_error_count < self.MAX_CONSECUTIVE_ERRORS
                    )

                    # For now, just return after error - no recursive recovery
                    # TODO: In the future, implement error recovery with conversation continuation
                    return

    def _execute_generated_code(self, arguments_str: str) -> tuple[go.Figure, str]:
        """Execute generated code and return figure and code

        Args:
            arguments_str: JSON string with function arguments

        Returns:
            Tuple of (figure, code)

        Raises:
            ValueError: If arguments are invalid
            RuntimeError: If code execution fails
        """
        # Parse arguments
        arguments = json.loads(arguments_str)
        code = arguments.get('code', '')

        if not code.strip():
            raise ValueError("No code provided in function arguments")

        # Execute code
        figure = self._execute_plotly_code(code)

        return figure, code

    def _execute_plotly_code(self, code: str) -> go.Figure:
        """Execute generated Plotly code and return figure

        Args:
            code: Python code to execute

        Returns:
            Plotly Figure object

        Raises:
            RuntimeError: If code execution fails
            ValueError: If code doesn't produce valid figure
        """
        if not code.strip():
            raise ValueError("No code provided")

        # Create safe execution environment
        execution_globals = {
            'df': self._dataframe,
            'pd': pd,
            'go': go,
            '__builtins__': __builtins__
        }

        # Execute the code
        try:
            exec(code, execution_globals)
        except Exception as exec_error:
            raise RuntimeError(f"Error executing generated code: {exec_error}")

        # Validate figure was created
        if 'fig' not in execution_globals:
            raise ValueError(
                "The executed code did not define a variable named 'fig'. "
                "Make sure to assign the plotly figure to a variable named 'fig'."
            )

        fig = execution_globals['fig']

        if not isinstance(fig, go.Figure):
            raise ValueError(
                "The 'fig' variable is not a Plotly figure. "
                "Make sure to assign a plotly Figure object to a variable named 'fig'."
            )

        return fig

    def _parse_function_arguments(self, event_data) -> Optional[str]:
        """Parse function arguments from OpenAI event"""
        if isinstance(
                event_data, ResponseOutputItemDoneEvent) and isinstance(
                event_data.item, ResponseFunctionToolCall):
            return event_data.item.arguments
        return None

    def _get_function_call_id(self, event_data) -> Optional[str]:
        """Get function call ID from OpenAI event"""
        if isinstance(
                event_data, ResponseOutputItemDoneEvent) and isinstance(
                event_data.item, ResponseFunctionToolCall):
            return event_data.item.call_id
        return None

    def _is_function_call_event(self, event_data) -> bool:
        """Check if event is a function call"""
        return (isinstance(event_data, ResponseOutputItemDoneEvent) and
                isinstance(event_data.item, ResponseFunctionToolCall))

    def _get_table_metadata(self) -> str:
        """Get table metadata for prompt creation

        Args:
            dataframe: DataFrame to analyze

        Returns:
            String containing table metadata
        """
        column_info = []
        for col in self._dataframe.columns:
            dtype = str(self._dataframe[col].dtype)
            column_info.append(f"{col}: {dtype}")

        return f"""Table Information:
- Columns ({len(self._dataframe.columns)}): {', '.join(column_info)}
- Number of rows: {len(self._dataframe)}
- Table shape: {self._dataframe.shape}"""

    def _create_plot_prompt(self, table_metadata: str) -> str:
        """Create prompt for OpenAI with table metadata

        Args:
            table_metadata: String containing table metadata

        Returns:
            Formatted prompt for OpenAI
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
