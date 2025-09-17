import json
from typing import Generator, List, Optional

import numpy as np
import pandas as pd
from gws_core import BaseModelDTO, Table
from openai import OpenAI
from openai.types.responses import ResponseFunctionToolCall
from pydantic import Field

from .base_function_agent_ai import BaseFunctionAgentAi
from .dataframe_transform_agent_ai_events import (DataFrameTransformAgentEvent,
                                                  ErrorEvent,
                                                  TableTransformEvent)


class DataFrameTransformConfig(BaseModelDTO):
    """Configuration for DataFrame transformation code generation"""
    code: str = Field(
        description="Python code to transform a DataFrame. The code should use a DataFrame variable named 'df' as input and assign the transformed result to a variable named 'transformed_df'.",
    )

    class Config:
        extra = "forbid"  # Prevent additional properties


class DataFrameTransformAgentAiDTO(BaseModelDTO):
    model: str
    temperature: float
    table_name: Optional[str] = None
    previous_response_id: str | None = None
    emitted_events: List[DataFrameTransformAgentEvent] = []


class DataFrameTransformAgentAi(BaseFunctionAgentAi[DataFrameTransformAgentEvent]):
    """Standalone DataFrame transform agent service for data manipulation using OpenAI"""

    _table: Table
    _table_name: Optional[str]

    def __init__(self, openai_client: OpenAI,
                 table: Table,
                 model: str,
                 temperature: float,
                 table_name: Optional[str] = None):
        super().__init__(openai_client, model, temperature)
        self._table = table
        self._table_name = table_name

    def _get_tools(self) -> List[dict]:
        """Get tools configuration for OpenAI"""
        return [
            {"type": "function", "name": "transform_dataframe",
             "description":
             "Generate Python code that transforms a DataFrame. The code should use 'df' as the input DataFrame variable and assign the result to 'transformed_df'.",
             "parameters": DataFrameTransformConfig.model_json_schema()}
        ]

    def _get_success_response(self) -> dict:
        """Get success response for function call output"""
        return {"Transform": "Successfully transformed the DataFrame."}

    def _get_error_response(self, error_message: str) -> dict:
        """Get error response for function call output"""
        return {"Transform": f"Error: {error_message}"}

    def _handle_function_call(self, event_item: ResponseFunctionToolCall,
                              current_response_id: str) -> Generator[DataFrameTransformAgentEvent, None, None]:
        """Handle output item done event"""
        # Handle function call completion

        function_args = event_item.arguments
        call_id = event_item.call_id

        if not function_args:
            yield ErrorEvent(
                message=str("No function arguments provided for DataFrame transformation."),
                code=None,
                call_id=call_id,
                error_type="execution_error",
            )
            return

        try:
            transformed_df, code = self._execute_generated_code(function_args)

            yield TableTransformEvent(
                table=Table(transformed_df),
                code=code,
                call_id=call_id,
                response_id=current_response_id,
                table_name=self._new_table_name
            )

            # Transform successful - no recursion needed
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

    def _execute_generated_code(self, arguments_str: str) -> tuple[pd.DataFrame, str]:
        """Execute generated code and return transformed DataFrame and code

        Args:
            arguments_str: JSON string with function arguments

        Returns:
            Tuple of (transformed_dataframe, code)

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

        # Validate transformed DataFrame was created
        if 'transformed_df' not in execution_globals:
            raise ValueError(
                "The executed code did not define a variable named 'transformed_df'. "
                "Make sure to assign the transformed DataFrame to a variable named 'transformed_df'."
            )

        transformed_df = execution_globals['transformed_df']

        if not isinstance(transformed_df, pd.DataFrame):
            raise ValueError(
                "The 'transformed_df' variable is not a pandas DataFrame. "
                "Make sure to assign a pandas DataFrame object to a variable named 'transformed_df'."
            )

        return transformed_df, code

    def _get_code_execution_globals(self) -> dict:
        """Get globals for code execution environment"""
        return {
            'pd': pd,
            'numpy': np,  # Include numpy as it's commonly used with pandas
            'np': np,
            '__builtins__': __builtins__
        }

    def _get_ai_instruction(self) -> str:
        """Create prompt for OpenAI with table metadata

        Returns:
            Formatted prompt for OpenAI
        """

        table_metadata = self._table.get_ai_description()
        return f"""You are an AI assistant specialized in data cleaning, transformation, and manipulation. You have access to information about a table/dataset but not the actual data.

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

    def to_dto(self) -> DataFrameTransformAgentAiDTO:
        """Convert agent state to DTO"""
        return DataFrameTransformAgentAiDTO(
            model=self._model,
            temperature=self._temperature,
            table_name=self._table_name,
            previous_response_id=self._previous_response_id,
            emitted_events=self._emitted_events.copy()  # Create a copy of the list
        )

    @classmethod
    def from_dto(cls, dto: DataFrameTransformAgentAiDTO, openai_client: OpenAI, table: Table) -> "DataFrameTransformAgentAi":
        """Create agent instance from DTO"""
        agent = cls(
            openai_client=openai_client,
            table=table,
            model=dto.model,
            temperature=dto.temperature,
            table_name=dto.table_name
        )
        agent._previous_response_id = dto.previous_response_id
        agent._emitted_events = dto.emitted_events.copy()  # Create a copy of the list
        return agent
