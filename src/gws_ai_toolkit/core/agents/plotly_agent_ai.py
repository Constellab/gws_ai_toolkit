from collections.abc import Generator

import pandas as pd
import plotly.graph_objects as go
from gws_core import BaseModelDTO, Table
from pydantic import Field

from gws_ai_toolkit.core.agents.base_function_agent_events import CodeEvent, FunctionCallEvent, FunctionErrorEvent

from .base_function_agent_ai import BaseFunctionAgentAi
from .plotly_agent_ai_events import PlotGeneratedEvent, PlotlyAgentEvent


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

    def __init__(
        self, openai_api_key: str, table: Table, model: str, temperature: float, skip_success_response: bool = False
    ):
        super().__init__(openai_api_key, model, temperature, skip_success_response=skip_success_response)
        self._table = table

    def _get_tools(self) -> list[dict]:
        """Get tools configuration for OpenAI"""
        return [
            {
                "type": "function",
                "name": "generate_plotly_figure",
                "description": "Generate Python code that creates a Plotly figure. The code should use 'df' as the DataFrame variable and return a Plotly Figure object.",
                "parameters": PlotlyCodeConfig.model_json_schema(),
            }
        ]

    def _handle_function_call(self, function_call_event: FunctionCallEvent) -> Generator[PlotlyAgentEvent, None, None]:
        """Handle function call event"""
        call_id = function_call_event.call_id
        response_id = function_call_event.response_id
        arguments = function_call_event.arguments

        # Use arguments dict directly (already parsed)
        code = arguments.get("code", "")

        if not code.strip():
            yield FunctionErrorEvent(
                message="No code provided in function arguments",
                call_id=call_id,
                response_id=response_id,
                agent_id=self.id,
            )
            return

        yield CodeEvent(
            code=code,
            call_id=call_id,
            response_id=response_id,
            agent_id=self.id,
        )

        try:
            figure = self._execute_generated_code(code)

            yield PlotGeneratedEvent(
                figure=figure,
                code=code,
                call_id=call_id,
                response_id=response_id,
                function_response="Successfully generated the plot.",
                agent_id=self.id,
            )

            # Plot generation successful - no recursion needed
            # The success response will be handled in the main loop
            return

        except Exception as exec_error:
            yield FunctionErrorEvent(
                message=str(exec_error),
                call_id=call_id,
                response_id=response_id,
                agent_id=self.id,
            )

            # Return after error - the main loop will handle retry logic
            return

    def _execute_generated_code(self, code: str) -> go.Figure:
        """Execute generated code and return figure

        Args:
            code: Python code to execute

        Returns:
            Tuple of (figure, code)

        Raises:
            ValueError: If arguments are invalid
            RuntimeError: If code execution fails
        """
        # Create safe execution environment
        execution_globals = self._get_code_execution_globals()
        execution_globals["df"] = self._table.get_data()

        # Execute the code
        try:
            exec(code, execution_globals)
        except Exception as exec_error:
            raise RuntimeError(f"Error executing generated code: {exec_error}")

        # Validate figure was created
        if "fig" not in execution_globals:
            raise ValueError(
                "The executed code did not define a variable named 'fig'. "
                "Make sure to assign the plotly figure to a variable named 'fig'."
            )

        fig = execution_globals["fig"]

        if not isinstance(fig, go.Figure):
            raise ValueError(
                "The 'fig' variable is not a Plotly figure. "
                "Make sure to assign a plotly Figure object to a variable named 'fig'."
            )

        return fig

    def _get_code_execution_globals(self) -> dict:
        """Get globals for code execution environment"""
        return {"pd": pd, "go": go, "__builtins__": __builtins__}

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
