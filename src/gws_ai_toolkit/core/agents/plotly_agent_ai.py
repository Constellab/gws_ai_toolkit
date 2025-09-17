import json
from typing import Generator, List, Optional

import pandas as pd
import plotly.graph_objects as go
from gws_core import BaseModelDTO
from openai import OpenAI
from openai.types.responses import (ResponseFunctionToolCall,
                                    ResponseOutputItemDoneEvent)
from pydantic import Field

from .plotly_agent_ai_events import (ErrorEvent, PlotAgentEvent,
                                     PlotGeneratedEvent,
                                     ResponseCompletedEvent,
                                     ResponseCreatedEvent, TextDeltaEvent)


class PlotlyCodeConfig(BaseModelDTO):
    """Configuration for Plotly code generation"""
    code: str = Field(
        description="Python code to generate a Plotly figure. The code should use a DataFrame variable named 'df' as input and return a Plotly Figure object.",
    )

    class Config:
        extra = "forbid"  # Prevent additional properties


class PlotlyAgentAi:
    """Standalone plot agent service for data visualization using OpenAI"""

    MAX_CONSECUTIVE_ERRORS = 5
    MAX_CONSECUTIVE_CALLS = 10

    _openai_client: OpenAI
    _dataframe: pd.DataFrame
    _model: str
    _temperature: float
    _previous_response_id: Optional[str]
    _emitted_events: List[PlotAgentEvent]

    def __init__(self, openai_client: OpenAI,
                 dataframe: pd.DataFrame,
                 model: str,
                 temperature: float):
        self._openai_client = openai_client
        self._dataframe = dataframe
        self._model = model
        self._temperature = temperature
        self._previous_response_id = None
        self._emitted_events = []
        self._success_inputs = None

    def generate_plot_stream(
        self,
        user_query: str,
    ) -> Generator[PlotAgentEvent, None, None]:
        """Generate plot with streaming events

        Args:
            user_query: User's request for visualization

        Yields:
            PlotAgentEvent: Stream of events during plot generation
        """
        consecutive_error_count = 0
        consecutive_call_count = 0

        messages = [{"role": "user", "content": [{"type": "input_text", "text": user_query}]}]

        # Main generation loop - replace recursion with iteration
        while (consecutive_error_count < self.MAX_CONSECUTIVE_ERRORS and
               consecutive_call_count < self.MAX_CONSECUTIVE_CALLS):
            consecutive_call_count += 1

            success_function_call_id: str | None = None
            error_event: ErrorEvent | None = None

            # Generate events for this attempt
            for event in self._generate_plot_stream_internal(messages):
                self._emitted_events.append(event)
                yield event

                if isinstance(event, PlotGeneratedEvent):
                    # Plot was successfully generated
                    success_function_call_id = event.call_id

                elif isinstance(event, ErrorEvent):
                    error_event = event

            # If plot was successfully generated, call OpenAI for success response
            # Update the current message and call openai in next iteration
            if success_function_call_id:
                messages = [{
                    "type": "function_call_output",
                    "call_id": success_function_call_id,
                    "output": json.dumps({
                        "Plot": "Successfully created the chart."
                    })
                }]
                continue

            # If there was an error during the function call, prepare error message for next iteration

            if error_event:
                consecutive_error_count += 1
                if not error_event.call_id:
                    # If no call_id, we cannot proceed with function call output
                    break
                messages = [
                    {
                        "type": "function_call_output",
                        "call_id": error_event.call_id,
                        "output": json.dumps({
                            "Plot": f"Error: {error_event.message}"
                        })
                    },
                    {"role": "user", "content": [{"type": "input_text", "text": "Can you fix the code?"}]}
                ]
                continue

            # If there were no function call (no plot) and no error, we are done
            if not success_function_call_id and not error_event:
                break

        if consecutive_error_count >= self.MAX_CONSECUTIVE_ERRORS:
            yield ErrorEvent(
                message=f"Maximum consecutive errors ({self.MAX_CONSECUTIVE_ERRORS}) reached",
                code=None,
                error_type="max_errors_reached",
            )

        if consecutive_call_count >= self.MAX_CONSECUTIVE_CALLS:
            yield ErrorEvent(
                message=f"Maximum consecutive calls ({self.MAX_CONSECUTIVE_CALLS}) reached",
                code=None,
                error_type="max_calls_reached",
            )

    def _generate_plot_stream_internal(
        self,
        input_messages: List[dict],
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
            previous_response_id=self._previous_response_id,
            tools=tools
        ) as stream:

            # Process streaming events
            for event in stream:
                # Yield streaming events to consumer
                if event.type == "response.output_text.delta":
                    yield TextDeltaEvent(delta=event.delta)

                elif event.type == "response.created":
                    current_response_id = event.response.id
                    yield ResponseCreatedEvent(response_id=current_response_id)
                elif event.type == "response.completed":
                    self._previous_response_id = event.response.id
                    yield ResponseCompletedEvent()
                elif event.type == "response.output_item.done":
                    for item_event in self._handle_output_item_done(event, current_response_id):
                        yield item_event

    def _handle_output_item_done(self, event: ResponseOutputItemDoneEvent,
                                 current_response_id: Optional[str]) -> Generator[PlotAgentEvent, None, None]:
        """Handle output item done event"""
        # Handle function call completion

        if not isinstance(event, ResponseOutputItemDoneEvent) or \
                not isinstance(event.item, ResponseFunctionToolCall):
            return

        function_args = event.item.arguments
        call_id = event.item.call_id

        if not function_args:
            yield ErrorEvent(
                message=str("No function arguments provided for plot generation."),
                code=None,
                call_id=call_id,
                error_type="execution_error",
            )
            return

        try:
            figure, code = self._execute_generated_code(function_args)

            yield PlotGeneratedEvent(
                figure=figure,
                code=code,
                call_id=call_id,
                response_id=current_response_id
            )

            # Plot generation successful - no recursion needed
            # The success response will be handled in the main loop
            return

        except Exception as exec_error:

            yield ErrorEvent(
                message=str(exec_error),
                code=None,
                call_id=call_id,
                error_type="execution_error",
            )

            # Return after error - the main loop will handle retry logic
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
        execution_globals = self._get_code_execution_globals()
        execution_globals['df'] = self._dataframe

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

    def _get_code_execution_globals(self) -> dict:
        """Get globals for code execution environment"""
        return {
            'pd': pd,
            # 'go': go,
            '__builtins__': __builtins__
        }

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
- Number of rows: {len(self._dataframe)}"""

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
- Do not call fig.show()

Call the function only once per user request for a chart.

Example code structure:
```python
fig = go.Figure()
# Add traces and configure layout
fig.add_trace(go.Scatter(x=df['column1'], y=df['column2']))
fig.update_layout(title='Chart Title')
```"""

    def get_emitted_events(self) -> List[PlotAgentEvent]:
        """Get all events emitted during the last generation"""
        return self._emitted_events
