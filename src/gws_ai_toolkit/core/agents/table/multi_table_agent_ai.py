import traceback
from collections.abc import Generator

import numpy as np
import pandas as pd
from gws_core import BaseModelDTO, Table
from pydantic import Field

from gws_ai_toolkit.core.agents.base_function_agent_events import CodeEvent, FunctionCallEvent
from gws_ai_toolkit.core.agents.code_execution_error import CodeExecutionError
from gws_ai_toolkit.core.agents.table.table_agent_ai_events import UserQueryMultiTablesEvent

from ..base_function_agent_ai import BaseFunctionAgentAi, FunctionErrorEvent
from .multi_table_agent_ai_events import MultiTableTransformAgentEvent, MultiTableTransformEvent


class MultiTableTransformConfig(BaseModelDTO):
    """Configuration for multi-table transformation code generation"""

    code: str = Field(
        description="Python code to transform multiple DataFrames. The code should use DataFrame variables that match the input table names and assign the transformed results to a dictionary named 'result_tables' where keys are descriptive table names and values are DataFrames.",
    )

    class Config:
        extra = "forbid"  # Prevent additional properties


class MultiTableAgentAi(
    BaseFunctionAgentAi[MultiTableTransformAgentEvent, UserQueryMultiTablesEvent]
):
    """Multi-table transform agent service for data manipulation using OpenAI"""

    def __init__(
        self,
        openai_api_key: str,
        model: str,
        temperature: float,
        skip_success_response: bool = False,
    ):
        super().__init__(
            openai_api_key, model, temperature, skip_success_response=skip_success_response
        )

    def _get_tools(self) -> list[dict]:
        """Get tools configuration for OpenAI"""
        return [
            {
                "type": "function",
                "name": "transform_multiple_tables",
                "description": "Generate Python code that transforms multiple DataFrames. The code should use DataFrame variables that match the input table names and store results in a dictionary named 'result_tables'.",
                "parameters": MultiTableTransformConfig.model_json_schema(),
            }
        ]

    def _handle_function_call(
        self, function_call_event: FunctionCallEvent, user_query: UserQueryMultiTablesEvent
    ) -> Generator[MultiTableTransformAgentEvent, None, None]:
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
            result_tables = self._execute_generated_code(code, user_query.tables)

            yield MultiTableTransformEvent(
                tables=result_tables,
                code=code,
                call_id=call_id,
                response_id=response_id,
                function_response="Successfully transformed the multiple tables.",
                agent_id=self.id,
            )

            # Transform successful - no recursion needed
            # The success response will be handled in the main loop
            return

        except CodeExecutionError as exec_error:
            # Extract stack trace from CodeExecutionError
            yield FunctionErrorEvent(
                message=exec_error.message,
                stack_trace=exec_error.stack_trace,
                call_id=call_id,
                response_id=response_id,
                agent_id=self.id,
            )
            # Return after error - the main loop will handle retry logic
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

    def _execute_generated_code(self, code: str, tables: dict[str, Table]) -> dict[str, Table]:
        """Execute generated code and return transformed tables

        Args:
            code: Python code to execute

        Returns:
            Dictionary of table names to Table objects

        Raises:
            ValueError: If code is invalid or doesn't produce expected output
            CodeExecutionError: If code execution fails (includes stack trace)
        """
        # Create safe execution environment
        execution_globals = self._get_code_execution_globals()

        # Add all tables to a dictionary for access by name
        tables_dict = {}
        for table_name, table in tables.items():
            tables_dict[table_name] = table.get_data()

        # Make tables accessible via the 'tables' dictionary
        execution_globals["tables"] = tables_dict

        # Execute the code
        try:
            exec(code, execution_globals)
        except Exception as exec_error:
            # Include stack trace in the exception for AI context
            error_msg = f"Error executing generated code: {exec_error}"
            stack_trace = traceback.format_exc()
            raise CodeExecutionError(error_msg, stack_trace) from exec_error

        # Validate result_tables dictionary was created
        if "result_tables" not in execution_globals:
            raise ValueError(
                "The executed code did not define a variable named 'result_tables'. "
                "Make sure to assign the transformed DataFrames to a dictionary named 'result_tables' "
                "where keys are table names and values are pandas DataFrames."
            )

        result_tables_dict = execution_globals["result_tables"]

        if not isinstance(result_tables_dict, dict):
            raise ValueError(
                "The 'result_tables' variable is not a dictionary. "
                "Make sure to assign a dictionary to a variable named 'result_tables'."
            )

        # Validate all values in the dictionary are DataFrames
        for key, value in result_tables_dict.items():
            if not isinstance(value, pd.DataFrame):
                raise ValueError(
                    f"The value for key '{key}' in 'result_tables' is not a pandas DataFrame. "
                    "Make sure all values in the 'result_tables' dictionary are pandas DataFrames."
                )

        # Convert DataFrames to Tables
        result_tables = {}
        for key, df in result_tables_dict.items():
            table = Table(df)
            table.name = key
            result_tables[key] = table

        return result_tables

    def _get_code_execution_globals(self) -> dict:
        """Get globals for code execution environment"""
        return {
            "pd": pd,
            "numpy": np,  # Include numpy as it's commonly used with pandas
            "np": np,
            "__builtins__": __builtins__,
        }

    def _get_ai_instruction(self, user_query: UserQueryMultiTablesEvent) -> str:
        """Create prompt for OpenAI with table metadata

        Returns:
            Formatted prompt for OpenAI
        """

        tables_info = user_query.get_tables_info()

        output_tables_instruction = ""
        if user_query.output_table_names:
            output_tables_instruction = f"""
# Expected Output Tables
The user expects the following output table names (use these as keys in the 'result_tables' dictionary):
{", ".join(f"'{name}'" for name in user_query.output_table_names)}
"""

        return f"""You are an AI assistant specialized in multi-table data operations, including joining, merging, transforming, and analyzing multiple datasets. You have access to information about multiple tables/datasets but not the actual data.

# Available Tables
{tables_info}
{output_tables_instruction}
Your role is to help users perform operations on multiple tables. When users request transformations, you should:

1. Generate Python code that works with multiple DataFrames
2. Ensure the code assigns the final result(s) to a dictionary named 'result_tables'
3. The 'result_tables' dictionary should have descriptive keys and pandas DataFrame values{" - use the expected output table names if provided above" if user_query.output_table_names else ""}
4. Use pandas operations for data manipulation and merging
5. Make reasonable assumptions about data based on column names and types
6. Handle potential data issues gracefully (missing values, data types, etc.)

You can assume the following imports are available:
- pandas as pd
- numpy as np

# Accessing Tables in Code
All tables are available via the `tables` dictionary. Access them using their original names:
- `tables['4_Order']` - for a table named '4_Order'
- `tables['metadata']` - for a table named 'metadata'
- etc.

Common multi-table operations you can perform:
- Data merging and joining (inner, outer, left, right joins)
- Data concatenation (row-wise or column-wise)
- Cross-table calculations and aggregations
- Data comparison and reconciliation
- Multi-table filtering and transformation
- Creating summary or pivot tables from multiple sources
- Data validation across tables

When generating code, make sure it:
- Creates meaningful transformations based on the data types and user request
- Handles potential data issues gracefully
- Assigns the final result(s) to a dictionary named 'result_tables'
- Uses descriptive keys for the result tables
- Does not use function definitions
- Does not use return statements
- Does not call print() or display functions

Call the function only once per user request for a transformation.

Example code structure for the available tables:
```python
# Access tables via the tables dictionary using their exact names from the 'Available Tables' section
# Example with two tables:
order_data = tables['4_Order']
meta_data = tables['metadata']

# Perform operations (e.g., merge/join)
merged_data = pd.merge(order_data, meta_data, left_on='index', right_on='sample-id', how='left')

# Always assign results to result_tables dictionary
result_tables = {{
    'merged_table': merged_data,
    'summary_table': merged_data.groupby('category').sum()
}}
```

Remember:
- Always access tables via `tables['table_name']` using the exact names from 'Available Tables' section
- Assign final results to the `result_tables` dictionary
- Use descriptive keys for the result tables"""
