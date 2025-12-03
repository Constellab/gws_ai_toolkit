from collections.abc import Generator

import numpy as np
import pandas as pd
from gws_core import BaseModelDTO, Table
from pydantic import Field

from gws_ai_toolkit.core.agents.base_function_agent_events import CodeEvent, FunctionCallEvent, FunctionErrorEvent
from gws_ai_toolkit.core.agents.table.table_agent_event_base import UserQueryTableTransformEvent

from ..base_function_agent_ai import BaseFunctionAgentAi
from .table_transform_agent_ai_events import DataFrameTransformAgentEvent, TableTransformEvent


class TableTransformConfig(BaseModelDTO):
    """Configuration for DataFrame transformation code generation"""

    code: str = Field(
        description="Python code to transform a DataFrame. The code should use a DataFrame variable named 'df' as input and assign the transformed result to a variable named 'transformed_df'.",
    )

    transformed_table_name: str = Field(
        description="Optional new name for the transformed table. Based on transformations and original table name (if provided). Keep it concise.",
    )

    class Config:
        extra = "forbid"  # Prevent additional properties


class TableTransformAgentAi(BaseFunctionAgentAi[DataFrameTransformAgentEvent, UserQueryTableTransformEvent]):
    """Standalone DataFrame transform agent service for data manipulation using OpenAI"""

    def __init__(
        self,
        openai_api_key: str,
        model: str,
        temperature: float,
        skip_success_response: bool = False,
    ):
        super().__init__(openai_api_key, model, temperature, skip_success_response=skip_success_response)

    def _get_tools(self) -> list[dict]:
        """Get tools configuration for OpenAI"""
        return [
            {
                "type": "function",
                "name": "transform_dataframe",
                "description": "Generate Python code that transforms a DataFrame. The code should use 'df' as the input DataFrame variable and assign the result to 'transformed_df'.",
                "parameters": TableTransformConfig.model_json_schema(),
            }
        ]

    def _handle_function_call(
        self, function_call_event: FunctionCallEvent, user_query: UserQueryTableTransformEvent
    ) -> Generator[DataFrameTransformAgentEvent, None, None]:
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

        transformed_table_name = user_query.output_table_name or arguments.get("transformed_table_name")
        if not transformed_table_name:
            yield FunctionErrorEvent(
                message="No transformed_table_name provided in function arguments",
                call_id=call_id,
                response_id=response_id,
                agent_id=self.id,
            )
            return

        try:
            transformed_df = self._execute_generated_code(code, user_query.table)

            table = Table(transformed_df)
            table.name = transformed_table_name

            yield TableTransformEvent(
                table=table,
                code=code,
                call_id=call_id,
                response_id=response_id,
                table_name=transformed_table_name,
                function_response="Successfully transformed the DataFrame.",
                agent_id=self.id,
            )

            # Transform successful - no recursion needed
            # The success response will be handled in the main loop
            return

        except Exception as exec_error:
            yield FunctionErrorEvent(
                message=str(exec_error), call_id=call_id, response_id=response_id, agent_id=self.id
            )

            # Return after error - the main loop will handle retry logic
            return

    def _execute_generated_code(self, code: str, table: Table) -> pd.DataFrame:
        """Execute generated code and return transformed DataFrame

        Args:
            code: Python code to execute
            table: Table to transform

        Returns:
            Transformed DataFrame

        Raises:
            ValueError: If code is invalid or doesn't produce expected output
            RuntimeError: If code execution fails
        """
        # Create safe execution environment
        execution_globals = self._get_code_execution_globals()
        execution_globals["df"] = table.get_data()

        # Execute the code
        try:
            exec(code, execution_globals)
        except Exception as exec_error:
            raise RuntimeError(f"Error executing generated code: {exec_error}")

        # Validate transformed DataFrame was created
        if "transformed_df" not in execution_globals:
            raise ValueError(
                "The executed code did not define a variable named 'transformed_df'. "
                "Make sure to assign the transformed DataFrame to a variable named 'transformed_df'."
            )

        transformed_df = execution_globals["transformed_df"]

        if not isinstance(transformed_df, pd.DataFrame):
            raise ValueError(
                "The 'transformed_df' variable is not a pandas DataFrame. "
                "Make sure to assign a pandas DataFrame object to a variable named 'transformed_df'."
            )

        return transformed_df

    def _get_code_execution_globals(self) -> dict:
        """Get globals for code execution environment"""
        return {
            "pd": pd,
            "numpy": np,  # Include numpy as it's commonly used with pandas
            "np": np,
            "__builtins__": __builtins__,
        }

    def _get_ai_instruction(self, user_query: UserQueryTableTransformEvent) -> str:
        """Create prompt for OpenAI with table metadata

        Args:
            user_query: User query event containing the table and metadata

        Returns:
            Formatted prompt for OpenAI
        """

        table_metadata = user_query.table.get_ai_description()
        table_name = f"Input table name : {user_query.table_name}" if user_query.table_name else ""
        output_table_name = f"Output table name: {user_query.output_table_name}" if user_query.output_table_name else ""
        return f"""You are an AI assistant specialized in data cleaning, transformation, and manipulation. You have access to information about a table/dataset but not the actual data.

{table_name}
{output_table_name}
{table_metadata}

Your role is to help users transform, clean, and manipulate this data. When users request data transformations, you should:

1. Generate Python code that transforms the DataFrame
2. Use 'df' as the variable name for the input DataFrame
3. Ensure the code assigns the final transformed result to a variable named 'transformed_df'
4. Use pandas operations for data manipulation
5. Make reasonable assumptions about data based on column names and types
6. Handle potential data issues gracefully (missing values, data types, etc.)

You can assume the following imports are available:
- pandas as pd
- numpy as np

Common transformation operations you can perform:
- Data cleaning (removing duplicates, handling missing values, data type conversions)
- Column operations (adding, removing, renaming, reordering columns)
- Row operations (filtering, sorting, grouping, aggregation)
- Data reshaping (pivot, melt, merge, join)
- String operations on text columns
- Date/time operations on datetime columns
- Mathematical operations on numeric columns

When generating code, make sure it:
- Uses 'df' as the input DataFrame variable
- Creates meaningful transformations based on the data types and user request
- Handles potential data issues gracefully
- Assigns the final result to a variable named 'transformed_df'
- Does not use function definitions
- Does not use return statements
- Does not call print() or display functions

Call the function only once per user request for a transformation.

Example code structure:
```python
# Perform transformations on df
transformed_df = df.copy()
# Apply specific transformations
transformed_df = transformed_df.dropna()
transformed_df['new_column'] = transformed_df['existing_column'] * 2
```"""
