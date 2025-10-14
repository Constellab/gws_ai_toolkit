import json
from typing import Generator, List, Optional

from gws_ai_toolkit.core.agents.base_function_agent_events import \
    FunctionSuccessEvent
from gws_ai_toolkit.core.agents.plotly_agent_ai_events import \
    PlotGeneratedEvent
from gws_ai_toolkit.core.agents.table_transform_agent_ai_events import \
    TableTransformEvent
from gws_core import BaseModelDTO, Table
from openai import OpenAI
from openai.types.responses import ResponseFunctionToolCall
from pydantic import Field

from .base_function_agent_ai import BaseFunctionAgentAi
from .plotly_agent_ai import PlotlyAgentAi
from .table_agent_ai_events import (FunctionErrorEvent, SubAgentSuccess,
                                    TableAgentEvent)
from .table_transform_agent_ai import TableTransformAgentAi


class PlotRequestConfig(BaseModelDTO):
    """Configuration for plot generation request"""
    user_request: str = Field(
        description="The user's request for data visualization. This will be passed to the plotting agent to generate appropriate charts."
    )

    class Config:
        extra = "forbid"


class TransformRequestConfig(BaseModelDTO):
    """Configuration for table transformation request"""
    user_request: str = Field(
        description="The user's request for data transformation. This will be passed to the transformation agent to generate appropriate code."
    )

    class Config:
        extra = "forbid"


class TableAgentAi(BaseFunctionAgentAi[TableAgentEvent]):
    """Main table agent that orchestrates plot and transformation operations using function calling"""

    _table: Table
    _table_name: Optional[str]

    def __init__(self, openai_client: OpenAI,
                 table: Table,
                 model: str,
                 temperature: float,
                 table_name: Optional[str] = None):
        super().__init__(openai_client, model, temperature, skip_success_response=False)
        self._table = table
        self._table_name = table_name

    def _get_tools(self) -> List[dict]:
        """Get tools configuration for OpenAI"""
        return [
            {
                "type": "function",
                "name": "generate_plot",
                "description": "Generate data visualizations and charts. Use this when the user wants to create plots, graphs, charts, or any visual representation of the data.",
                "parameters": PlotRequestConfig.model_json_schema()
            },
            {
                "type": "function",
                "name": "transform_table",
                "description": "Transform, clean, or manipulate table data. Use this when the user wants to modify the data structure, filter rows, add/remove columns, perform calculations, or any data manipulation tasks.",
                "parameters": TransformRequestConfig.model_json_schema()
            }
        ]

    def _handle_function_call(self, event_item: ResponseFunctionToolCall,
                              current_response_id: str) -> Generator[TableAgentEvent, None, None]:
        """Handle function call by delegating to appropriate specialized agent"""

        function_name = event_item.name
        function_args = event_item.arguments
        call_id = event_item.call_id

        if not function_args:
            yield FunctionErrorEvent(
                message=f"No function arguments provided for {function_name}.",
                call_id=call_id,
                response_id=current_response_id
            )
            return

        try:
            # Parse function arguments
            arguments = json.loads(function_args)
            user_request = arguments.get('user_request', '')

            if not user_request.strip():
                yield FunctionErrorEvent(
                    message="No user request provided in function arguments.",
                    call_id=call_id,
                    response_id=current_response_id
                )
                return

            if function_name == "generate_plot":
                plotly_agent = PlotlyAgentAi(
                    openai_client=self._openai_client,
                    table=self._table,
                    model=self._model,
                    temperature=self._temperature,
                    # skip success to avoid double success events because
                    # the main agent will handle it
                    skip_success_response=True
                )
                yield from self._handle_request(plotly_agent, user_request, call_id, current_response_id)
            elif function_name == "transform_table":
                transform_agent = TableTransformAgentAi(
                    openai_client=self._openai_client,
                    table=self._table,
                    model=self._model,
                    temperature=self._temperature,
                    table_name=self._table_name,
                    # skip success to avoid double success events because
                    # the main agent will handle it
                    skip_success_response=True
                )
                yield from self._handle_request(transform_agent, user_request, call_id, current_response_id)
            else:
                yield FunctionErrorEvent(
                    message=f"Unknown function: {function_name}",
                    call_id=call_id,
                    response_id=current_response_id
                )

        except json.JSONDecodeError as e:
            yield FunctionErrorEvent(
                message=f"Invalid JSON in function arguments: {e}",
                call_id=call_id,
                response_id=current_response_id
            )
        except Exception as e:
            yield FunctionErrorEvent(
                message=f"Error handling {function_name}: {e}",
                call_id=call_id,
                response_id=current_response_id
            )

    def _handle_request(self,
                        ai_agent: BaseFunctionAgentAi,
                        user_request: str,
                        call_id: str,
                        response_id: str) -> Generator[TableAgentEvent, None, None]:
        """Handle plot generation request by delegating to PlotlyAgentAi"""

        # Set the last response ID to maintain conversation context
        # plot_agent.set_last_response_id(self.get_last_response_id())

        # Delegate to plot agent and yield events directly
        success_event: Optional[FunctionSuccessEvent] = None
        table_event: Optional[TableTransformEvent] = None
        for event in ai_agent.call_agent(user_request):
            yield event
            # If we get a FunctionSuccessEvent, we can yield a SubAgentSuccess
            if isinstance(event, FunctionSuccessEvent):
                success_event = event

            if isinstance(event, TableTransformEvent):
                table_event = event

        if table_event:
            # Update internal table reference if transformed
            self._set_table(table_event.table, table_event.table_name)

        if success_event:
            yield SubAgentSuccess(
                call_id=call_id,
                response_id=response_id,
                function_response=f"{success_event.function_response} Continue with next steps if needed."
            )

    def _set_table(self, table: Table, table_name: Optional[str] = None):
        """Update the internal table reference"""
        self._table = table
        if table_name:
            self._table_name = table_name
        else:
            self._table_name = table.name

    def _get_ai_instruction(self) -> str:
        """Create prompt for OpenAI with table metadata"""

        table_metadata = self._table.get_ai_description()
        table_name = f"Table name: {self._table_name}" if self._table_name else ""

        return f"""You are an AI assistant specialized in table operations including data analysis, visualization, and manipulation. You have access to information about a table/dataset but not the actual data.

{table_name}
{table_metadata}

You can help users with two main types of operations:

1. **Data Visualization** - Use the `generate_plot` function when users want to:
   - Create charts, graphs, or plots
   - Visualize data patterns or relationships
   - Generate statistical visualizations
   - Create interactive dashboards

2. **Data Transformation** - Use the `transform_table` function when users want to:
   - Clean or modify data
   - Filter rows or select columns
   - Perform calculations or aggregations
   - Restructure or reshape data
   - Handle missing values
   - Create new derived columns

**Important Guidelines:**
- Analyze the user's request carefully to determine if they want visualization OR transformation
- Choose the appropriate function based on the user's intent
- Pass the complete user request to the selected function
- **CRITICAL: Call EXACTLY ONE function per response - NEVER call multiple functions simultaneously**
- **If the user requests multiple operations in sequence (e.g., "multiply columns by 10, then make a scatter plot"):**
  - Identify the FIRST operation that needs to be performed (in this case: transformation)
  - Call ONLY that function (transform_table)
  - The user will provide new input after this operation completes to request the next step
- **Sequential Processing**: Data transformations must be completed before visualizations can use the transformed data
- Be specific about what the user wants to achieve with the current function call

**Examples:**
- "Show me a scatter plot of X vs Y" → Use `generate_plot`
- "Create a bar chart of sales by region" → Use `generate_plot`
- "Remove rows with missing values" → Use `transform_table`
- "Add a new column calculating profit margin" → Use `transform_table`
- "Filter the data to show only records from 2023" → Use `transform_table`

**Sequential Request Examples (ONLY do the FIRST operation):**
- "Multiply all columns by 10, then make a scatter plot" → Call ONLY `transform_table` with "Multiply all columns by 10"
- "Filter data for 2023, then create a bar chart" → Call ONLY `transform_table` with "Filter data for 2023"
- "Add profit column, then show distribution plot" → Call ONLY `transform_table` with "Add profit column"

You should call the appropriate function based on the user's request and let the specialized agent handle the detailed implementation."""
