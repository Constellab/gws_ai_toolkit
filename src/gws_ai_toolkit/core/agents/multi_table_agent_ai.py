import json
from collections.abc import Generator

import numpy as np
import pandas as pd
from gws_core import BaseModelDTO, Table
from openai.types.responses import ResponseFunctionToolCall
from pydantic import Field

from gws_ai_toolkit.core.agents.base_function_agent_events import CodeEvent

from .base_function_agent_ai import BaseFunctionAgentAi, FunctionErrorEvent
from .multi_table_agent_ai_events import MultiTableTransformAgentEvent, MultiTableTransformEvent


class MultiTableTransformConfig(BaseModelDTO):
    """Configuration for multi-table transformation code generation"""

    code: str = Field(
        description="Python code to transform multiple DataFrames. The code should use DataFrame variables that match the input table names and assign the transformed results to variables with meaningful names. Results should be stored in a dictionary named 'result_tables' where keys are table names and values are DataFrames.",
    )

    result_table_names: list[str] | None = Field(
        default=None,
        description="Optional list of names for the resulting tables. Should match the keys in result_tables dictionary. Keep names concise and descriptive.",
    )

    class Config:
        extra = "forbid"  # Prevent additional properties


class MultiTableAgentAi(BaseFunctionAgentAi[MultiTableTransformAgentEvent]):
    """Multi-table transform agent service for data manipulation using OpenAI"""

    _tables: dict[str, Table]
    _table_names: list[str]

    def __init__(
        self,
        openai_api_key: str,
        tables: dict[str, Table],
        model: str,
        temperature: float,
        skip_success_response: bool = False,
    ):
        super().__init__(openai_api_key, model, temperature, skip_success_response=skip_success_response)
        self._tables = tables
        self._table_names = list(tables.keys())

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
        self, event_item: ResponseFunctionToolCall, current_response_id: str
    ) -> Generator[MultiTableTransformAgentEvent, None, None]:
        """Handle output item done event"""
        # Handle function call completion

        function_args = event_item.arguments
        call_id = event_item.call_id

        if not function_args:
            yield FunctionErrorEvent(
                message="No function arguments provided for multi-table transformation.",
                call_id=call_id,
                response_id=current_response_id,
            )
            return

        # Parse arguments
        arguments = json.loads(function_args)
        code = arguments.get("code", "")

        if not code.strip():
            yield FunctionErrorEvent(
                message="No code provided in function arguments",
                call_id=call_id,
                response_id=current_response_id,
            )
            return

        yield CodeEvent(
            code=code,
            call_id=call_id,
            response_id=current_response_id,
        )

        try:
            result_tables = self._execute_generated_code(code)

            result_table_names = arguments.get("result_table_names", list(result_tables.keys()))

            yield MultiTableTransformEvent(
                tables=result_tables,
                code=code,
                call_id=call_id,
                response_id=current_response_id,
                table_names=result_table_names,
                function_response="Successfully transformed the multiple tables.",
            )

            # Transform successful - no recursion needed
            # The success response will be handled in the main loop
            return

        except Exception as exec_error:
            yield FunctionErrorEvent(message=str(exec_error), call_id=call_id, response_id=current_response_id)

            # Return after error - the main loop will handle retry logic
            return

    def _execute_generated_code(self, code: str) -> dict[str, Table]:
        """Execute generated code and return transformed tables

        Args:
            code: Python code to execute

        Returns:
            Dictionary of table names to Table objects

        Raises:
            ValueError: If code is invalid or doesn't produce expected output
            RuntimeError: If code execution fails
        """
        # Create safe execution environment
        execution_globals = self._get_code_execution_globals()

        # Add all input tables to the execution environment
        for table_name, table in self._tables.items():
            execution_globals[table_name] = table.get_data()

        # Execute the code
        try:
            exec(code, execution_globals)
        except Exception as exec_error:
            raise RuntimeError(f"Error executing generated code: {exec_error}")

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
            result_tables[key] = Table(df)

        return result_tables

    def _get_code_execution_globals(self) -> dict:
        """Get globals for code execution environment"""
        return {
            "pd": pd,
            "numpy": np,  # Include numpy as it's commonly used with pandas
            "np": np,
            "__builtins__": __builtins__,
        }

    def _get_ai_instruction(self) -> str:
        """Create prompt for OpenAI with table metadata

        Returns:
            Formatted prompt for OpenAI
        """

        tables_metadata = []
        for table_name, table in self._tables.items():
            table_metadata = table.get_ai_description()
            tables_metadata.append(f"Table '{table_name}':\n{table_metadata}")

        tables_info = "\n\n".join(tables_metadata)
        table_names_list = ", ".join(self._table_names)

        return f"""You are an AI assistant specialized in multi-table data operations, including joining, merging, transforming, and analyzing multiple datasets. You have access to information about multiple tables/datasets but not the actual data.

Available tables: {table_names_list}

{tables_info}

Your role is to help users perform operations on multiple tables. When users request transformations, you should:

1. Generate Python code that works with multiple DataFrames
2. Use the exact table names as variable names for the input DataFrames: {table_names_list}
3. Ensure the code assigns the final result(s) to a dictionary named 'result_tables'
4. The 'result_tables' dictionary should have descriptive keys and pandas DataFrame values
5. Use pandas operations for data manipulation and merging
6. Make reasonable assumptions about data based on column names and types
7. Handle potential data issues gracefully (missing values, data types, etc.)

You can assume the following imports are available:
- pandas as pd
- numpy as np

Common multi-table operations you can perform:
- Data merging and joining (inner, outer, left, right joins)
- Data concatenation (row-wise or column-wise)
- Cross-table calculations and aggregations
- Data comparison and reconciliation
- Multi-table filtering and transformation
- Creating summary or pivot tables from multiple sources
- Data validation across tables

When generating code, make sure it:
- Uses the exact table names as DataFrame variables: {table_names_list}
- Creates meaningful transformations based on the data types and user request
- Handles potential data issues gracefully
- Assigns the final result(s) to a dictionary named 'result_tables'
- Uses descriptive keys for the result tables
- Does not use function definitions
- Does not use return statements
- Does not call print() or display functions

Call the function only once per user request for a transformation.

Example code structure:
```python
# Work with multiple input DataFrames
# Available DataFrames: {table_names_list}

# Example: Join two tables
merged_data = pd.merge({self._table_names[0] if self._table_names else "table1"}, {self._table_names[1] if len(self._table_names) > 1 else "table2"}, on='common_column', how='inner')

# Example: Create multiple result tables
result_tables = {{
    'merged_table': merged_data,
    'summary_table': merged_data.groupby('category').sum()
}}
```"""
