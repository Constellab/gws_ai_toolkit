import json
from typing import Generator, List

import pandas as pd
import plotly.graph_objects as go
from gws_core import BaseModelDTO, Table
from openai import OpenAI
from openai.types.responses import ResponseFunctionToolCall
from pydantic import Field

from .base_function_agent_ai import BaseFunctionAgentAi
from .plotly_agent_ai_events import (ErrorEvent, PlotGeneratedEvent,
                                     PlotlyAgentEvent)


class PlotlyCodeConfig(BaseModelDTO):
    """Configuration for Plotly code generation"""
    code: str = Field(
        description="Python code to generate a Plotly figure. The code should use a DataFrame variable named 'df' as input and return a Plotly Figure object.",
    )

    class Config:
        extra = "forbid"  # Prevent additional properties


class PlotlyAgentAi(BaseFunctionAgentAi[PlotlyAgentEvent]):
    """Standalone plot agent service for data visualization using OpenAI"""

    _table: Table

    def __init__(self, openai_client: OpenAI,
                 table: Table,
                 model: str,
                 temperature: float):
        super().__init__(openai_client, model, temperature)
        self._table = table

    def _get_tools(self) -> List[dict]:
        """Get tools configuration for OpenAI"""
        return [
            {"type": "function", "name": "generate_plotly_figure",
             "description":
             "Generate Python code that creates a Plotly figure. The code should use 'df' as the DataFrame variable and return a Plotly Figure object.",
             "parameters": PlotlyCodeConfig.model_json_schema()}
        ]

    def _get_success_response(self) -> dict:
        """Get success response for function call output"""
        return {"Plot": "Successfully created the chart."}

    def _get_error_response(self, error_message: str) -> dict:
        """Get error response for function call output"""
        return {"Plot": f"Error: {error_message}"}

    def _handle_function_call(self, event_item: ResponseFunctionToolCall,
                              current_response_id: str) -> Generator[PlotlyAgentEvent, None, None]:
        """Handle output item done event"""
        # Handle function call completion

        function_args = event_item.arguments
        call_id = event_item.call_id

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

        # Create safe execution environment
        execution_globals = self._get_code_execution_globals()
        execution_globals['df'] = self._table.get_data()

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

        return fig, code

    def _get_code_execution_globals(self) -> dict:
        """Get globals for code execution environment"""
        return {
            'pd': pd,
            'go': go,
            '__builtins__': __builtins__
        }

    def _get_ai_instruction(self) -> str:
        """Create prompt for OpenAI with table metadata

        Returns:
            Formatted prompt for OpenAI
        """

        table_metadata = self._table.get_ai_description()
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
