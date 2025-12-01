from collections.abc import Generator

from gws_core import BaseModelDTO, Table
from pydantic import Field

from gws_ai_toolkit.core.agents.base_function_agent_events import (
    FunctionCallEvent,
    FunctionErrorEvent,
)
from gws_ai_toolkit.core.agents.table_transform_agent_ai_events import TableTransformEvent

from .base_function_agent_ai import BaseFunctionAgentAi
from .multi_table_agent_ai import MultiTableAgentAi
from .multi_table_agent_ai_events import MultiTableTransformEvent
from .plotly_agent_ai import PlotlyAgentAi
from .table_agent_ai_events import TableAgentEvent
from .table_transform_agent_ai import TableTransformAgentAi


class PlotRequestConfig(BaseModelDTO):
    """Configuration for plot generation request"""

    table_name: str = Field(
        description="The unique name of the table to use for plotting. This must match one of the available tables."
    )
    user_request: str = Field(
        description="The user's request for data visualization. This will be passed to the plotting agent to generate appropriate charts."
    )

    class Config:
        extra = "forbid"


class TransformRequestConfig(BaseModelDTO):
    """Configuration for table transformation request"""

    table_name: str = Field(
        description="The unique name of the table to transform. This must match one of the available tables."
    )
    output_table_name: str = Field(
        description="A unique name for the output/transformed table. This will be used to identify the transformed table in subsequent operations. It must not conflict with existing table names."
    )
    user_request: str = Field(
        description="The user's request for data transformation. This will be passed to the transformation agent to generate appropriate code."
    )

    class Config:
        extra = "forbid"


class MultiTableTransformRequestConfig(BaseModelDTO):
    """Configuration for multi-table transformation request"""

    table_names: list[str] = Field(
        description="List of table names to use for the transformation. All tables must exist in the available tables."
    )
    output_table_names: list[str] = Field(
        description="List of unique names for the output/transformed tables. These will be used to identify the transformed tables in subsequent operations."
    )
    user_request: str = Field(
        description="The user's request for multi-table transformation (e.g., merging, joining, comparing multiple tables). This will be passed to the multi-table transformation agent to generate appropriate code."
    )

    class Config:
        extra = "forbid"


class TableAgentAi(BaseFunctionAgentAi[TableAgentEvent]):
    """Main table agent that orchestrates plot and transformation operations using function calling"""

    _tables: dict[str, Table]

    def __init__(
        self,
        openai_api_key: str,
        model: str,
        temperature: float,
        table: Table | None = None,
        table_unique_name: str | None = None,
    ):
        super().__init__(openai_api_key, model, temperature, skip_success_response=False)
        self._tables = {}
        if table:
            table_unique_name = table_unique_name or table.name or "table"
            self.add_table(table_unique_name, table)

    def _get_tools(self) -> list[dict]:
        """Get tools configuration for OpenAI"""
        return [
            {
                "type": "function",
                "name": "generate_plot",
                "description": "Generate data visualizations and charts for a SINGLE table. Use this when the user wants to create plots, graphs, charts, or any visual representation of the data. Note: This function only supports operations on ONE table at a time.",
                "parameters": PlotRequestConfig.model_json_schema(),
            },
            {
                "type": "function",
                "name": "transform_table",
                "description": "Transform, clean, or manipulate a SINGLE table's data. Use this when the user wants to modify the data structure, filter rows, add/remove columns, perform calculations, or any data manipulation tasks. Note: This function only supports operations on ONE table at a time.",
                "parameters": TransformRequestConfig.model_json_schema(),
            },
            {
                "type": "function",
                "name": "transform_multiple_tables",
                "description": "Transform, merge, join, or manipulate MULTIPLE tables together. Use this when the user wants to combine data from multiple tables, perform cross-table operations, merge/join tables, or any operation that requires working with multiple tables simultaneously.",
                "parameters": MultiTableTransformRequestConfig.model_json_schema(),
            },
        ]

    def _handle_function_call(self, function_call_event: FunctionCallEvent) -> Generator[TableAgentEvent, None, None]:
        """Handle function call by delegating to appropriate specialized agent"""

        function_name = function_call_event.function_name
        call_id = function_call_event.call_id
        response_id = function_call_event.response_id
        arguments = function_call_event.arguments

        try:
            # Use arguments dict directly (already parsed)
            user_request = arguments.get("user_request", "")

            if not user_request.strip():
                yield FunctionErrorEvent(
                    message="No user request provided in function arguments.",
                    call_id=call_id,
                    response_id=response_id,
                    agent_id=self.id,
                )
                return

            if function_name == "generate_plot":
                yield from self._handle_plot_request(user_request, arguments, call_id, response_id)
            elif function_name == "transform_table":
                yield from self._handle_transform_request(user_request, arguments, call_id, response_id)
            elif function_name == "transform_multiple_tables":
                yield from self._handle_multi_table_transform_request(user_request, arguments, call_id, response_id)
            else:
                yield FunctionErrorEvent(
                    message=f"Unknown function: {function_name}",
                    call_id=call_id,
                    response_id=response_id,
                    agent_id=self.id,
                )
        except Exception as e:
            yield FunctionErrorEvent(
                message=f"Error handling {function_name}: {e}",
                call_id=call_id,
                response_id=response_id,
                agent_id=self.id,
            )

    def _handle_plot_request(
        self, user_request: str, arguments: dict, call_id: str, response_id: str
    ) -> Generator[TableAgentEvent, None, None]:
        """Handle plot generation request by creating and delegating to PlotlyAgentAi"""

        table_name = arguments.get("table_name", "")
        table: Table
        try:
            table = self._get_and_check_table(table_name)
        except Exception as e:
            yield FunctionErrorEvent(
                message=str(e),
                call_id=call_id,
                response_id=response_id,
                agent_id=self.id,
            )
            return

        # Create the plotly agent
        plotly_agent = PlotlyAgentAi(
            openai_api_key=self._openai_api_key,
            table=table,
            model=self._model,
            temperature=self._temperature,
            # skip success to avoid double success events because
            # the main agent will handle it
            skip_success_response=True,
        )

        yield from self.call_sub_agent(plotly_agent, user_request, response_id, call_id, self.id)

    def _handle_transform_request(
        self,
        user_request: str,
        arguments: dict,
        call_id: str,
        response_id: str,
    ) -> Generator[TableAgentEvent, None, None]:
        """Handle table transformation request by creating and delegating to TableTransformAgentAi"""

        table_name = arguments.get("table_name", "")
        table: Table
        try:
            table = self._get_and_check_table(table_name)
        except Exception as e:
            yield FunctionErrorEvent(
                message=str(e),
                call_id=call_id,
                response_id=response_id,
                agent_id=self.id,
            )
            return

        output_table_name = arguments.get("output_table_name", "")
        if not output_table_name.strip():
            yield FunctionErrorEvent(
                message="No output_table_name provided in function arguments.",
                call_id=call_id,
                response_id=response_id,
                agent_id=self.id,
            )
            return

        # Create the transform agent
        transform_agent = TableTransformAgentAi(
            openai_api_key=self._openai_api_key,
            table=table,
            model=self._model,
            temperature=self._temperature,
            table_name=table_name,
            output_table_name=output_table_name,
            # skip success to avoid double success events because
            # the main agent will handle it
            skip_success_response=True,
        )

        # Delegate to transform agent and yield events directly
        for event in self.call_sub_agent(transform_agent, user_request, response_id, call_id, self.id):
            yield event

            if isinstance(event, TableTransformEvent):
                self.add_table(output_table_name, event.table)

    def _handle_multi_table_transform_request(
        self, user_request: str, arguments: dict, call_id: str, response_id: str
    ) -> Generator[TableAgentEvent, None, None]:
        """Handle multi-table transformation request by creating and delegating to MultiTableAgentAi"""

        table_names = arguments.get("table_names", [])
        output_table_names = arguments.get("output_table_names", [])

        if not table_names:
            yield FunctionErrorEvent(
                message="No table_names provided in function arguments.",
                agent_id=self.id,
                call_id=call_id,
                response_id=response_id,
            )
            return

        if not output_table_names:
            yield FunctionErrorEvent(
                message="No output_table_names provided in function arguments.",
                agent_id=self.id,
                call_id=call_id,
                response_id=response_id,
            )
            return

        # Validate all input tables exist
        missing_tables = [name for name in table_names if name not in self._tables]
        if missing_tables:
            yield FunctionErrorEvent(
                message=f"Tables not found: {', '.join(missing_tables)}. Available tables: {', '.join(self._tables.keys())}",
                call_id=call_id,
                response_id=response_id,
                agent_id=self.id,
            )
            return

        # Get the requested tables
        input_tables = {name: self._tables[name] for name in table_names}

        # Create the multi-table transform agent
        multi_table_agent = MultiTableAgentAi(
            openai_api_key=self._openai_api_key,
            tables=input_tables,
            model=self._model,
            temperature=self._temperature,
            # skip success to avoid double success events because
            # the main agent will handle it
            skip_success_response=True,
        )

        # Delegate to multi-table agent and yield events directly
        for event in self.call_sub_agent(multi_table_agent, user_request, response_id, call_id, self.id):
            yield event

            if isinstance(event, MultiTableTransformEvent):
                for i, (result_table_name, result_table) in enumerate(event.tables.items()):
                    # Use provided output names if available, otherwise use the result table names from the event
                    if i < len(output_table_names):
                        self.add_table(output_table_names[i], result_table)
                    else:
                        self.add_table(result_table_name, result_table)

    def _get_and_check_table(self, table_unique_name: str) -> Table:
        # Retrieve the specified table
        if not table_unique_name or not table_unique_name.strip():
            raise Exception("No table name provided in function arguments.")

        table_unique_name = table_unique_name.strip()
        if table_unique_name not in self._tables:
            raise Exception(
                f"Table '{table_unique_name}' not found. Available tables: {', '.join(self._tables.keys())}"
            )
        return self._tables[table_unique_name]

    def _get_ai_instruction(self) -> str:
        """Create prompt for OpenAI with table metadata"""

        # Generate table information for all tables
        tables_info = "\n".join(
            [self._get_table_ai_info(table_name, table) for table_name, table in self._tables.items()]
        )

        return f"""You are an AI assistant specialized in table operations including data analysis, visualization, and manipulation. You have access to information about multiple tables/datasets but not the actual data.

# Available Tables
{tables_info}

You can help users with three main types of operations:

1. **Data Visualization** - Use the `generate_plot` function when users want to:
   - Create charts, graphs, or plots
   - Visualize data patterns or relationships
   - Generate statistical visualizations
   - Create interactive dashboards
   - **Note: This function only supports operations on ONE table at a time**

2. **Single Table Transformation** - Use the `transform_table` function when users want to:
   - Clean or modify data in one table
   - Filter rows or select columns
   - Perform calculations or aggregations on one table
   - Restructure or reshape a single table
   - Handle missing values
   - Create new derived columns
   - **Note: This function only supports operations on ONE table at a time**

3. **Multi-Table Transformation** - Use the `transform_multiple_tables` function when users want to:
   - Merge or join multiple tables together
   - Combine data from multiple tables
   - Perform cross-table operations
   - Compare or reconcile data across tables
   - Create summary tables from multiple sources
   - **Note: This function can work with MULTIPLE tables simultaneously**

**Important Guidelines:**
- Analyze the user's request carefully to determine if they want visualization, single-table transformation, OR multi-table transformation
- Choose the appropriate function based on the user's intent
- For single table operations: specify the table_name and output_table_name
- For multi-table operations: specify table_names (list) and output_table_names (list)
- Pass the complete user request to the selected function
- **CRITICAL: Call EXACTLY ONE function per response - NEVER call multiple functions simultaneously**
- **If the user requests multiple operations in sequence (e.g., "multiply columns by 10, then make a scatter plot"):**
  - Identify the FIRST operation that needs to be performed (in this case: transformation)
  - Call ONLY that function (transform_table)
  - The user will provide new input after this operation completes to request the next step
- **Sequential Processing**: Data transformations must be completed before visualizations can use the transformed data
- Be specific about what the user wants to achieve with the current function call

**Examples:**
- "Show me a scatter plot of X vs Y" → Use `generate_plot` with the appropriate table_name
- "Create a bar chart of sales by region" → Use `generate_plot` with the appropriate table_name
- "Remove rows with missing values from sales_data" → Use `transform_table` with table_name and output_table_name
- "Add a new column calculating profit margin" → Use `transform_table` with table_name and output_table_name
- "Merge sales_data and inventory_data on product column" → Use `transform_multiple_tables` with table_names=['sales_data', 'inventory_data'] and output_table_names
- "Join customer_data with orders_data and calculate total spending" → Use `transform_multiple_tables`
- "Compare sales between Q1_data and Q2_data" → Use `transform_multiple_tables`

**Sequential Request Examples (ONLY do the FIRST operation):**
- "Multiply all columns by 10, then make a scatter plot" → Call ONLY `transform_table` with table_name, output_table_name, and "Multiply all columns by 10"
- "Filter data for 2023, then create a bar chart" → Call ONLY `transform_table` with table_name, output_table_name, and "Filter data for 2023"
- "Merge sales and inventory, then filter for low stock" → Call ONLY `transform_multiple_tables` with "Merge sales and inventory"

You should call the appropriate function based on the user's request and let the specialized agent handle the detailed implementation.
If you don't have enough information to determine the user's intent, ask clarifying questions instead of making assumptions."""

    def _get_table_ai_info(self, table_unique_name: str, table: Table) -> str:
        """Get AI info string for a specific table"""
        table_name = f"## '{table_unique_name}'"
        table_description = table.get_ai_description()
        return f"""{table_name}
{table_description}
"""

    def clear_tables(self):
        """Clear all tables from the agent's table dictionary"""
        self._tables.clear()

    def add_table(self, table_unique_name: str, table: Table):
        """Add a new table to the agent's table dictionary"""
        self._tables[table_unique_name.strip()] = table

    def get_tables(self) -> dict[str, Table]:
        """Get all tables managed by the agent"""
        return self._tables
