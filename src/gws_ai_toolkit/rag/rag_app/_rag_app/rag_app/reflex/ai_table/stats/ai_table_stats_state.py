
import json
import os
from typing import List, Optional, Tuple

import reflex as rx
from gws_core import Table, TableUnfolderHelper
from openai import OpenAI
from pandas import DataFrame

from ..ai_table_data_state import AiTableDataState
from .ai_table_stats_class import AiTableStats


class AiTableStatsState(rx.State):
    """State for the AI Table stats component."""

    test_history_json: str = ""
    last_test_json: str = ""
    ai_prompt: str = ""
    is_processing: bool = False

    @rx.event(background=True)
    async def process_ai_prompt(self, form_data: dict):
        return await self._process_ai_prompt(form_data)

    async def _process_ai_prompt(self, form_data: dict):
        """Process AI prompt to extract column analysis parameters."""
        prompt = form_data.get("ai_prompt", "").strip()
        if not prompt:
            return rx.toast.error("Please enter a prompt describing your analysis.")

        current_df: DataFrame | None
        async with self:

            # Get current dataframe to extract column names
            ai_table_state = await self.get_state(AiTableDataState)
            current_df = ai_table_state.current_dataframe

        if current_df is None or current_df.empty:
            return rx.toast.error("No dataframe available. Please load a file first.")

        async with self:
            self.ai_prompt = prompt
            self.is_processing = True

            # Get current dataframe to extract column names
            ai_table_state = await self.get_state(AiTableDataState)

        available_columns = list(current_df.columns)

        # Convert prompt to analysis parameters using OpenAI
        columns_input, group_input, columns_are_paired = await self._convert_prompt_to_analysis_params(
            prompt=prompt,
            available_columns=available_columns
        )

        async with self:
            self.is_processing = False

        if not columns_input:
            return rx.toast.error(
                "Could not extract valid column names from the prompt. "
                "Please check your prompt and ensure you reference existing column names.")

        # Call the validation and analysis function
        return await self.validate_and_run_analysis(
            current_df=current_df,
            columns_input=columns_input,
            group_input=group_input,
            columns_are_paired=columns_are_paired
        )

    async def _convert_prompt_to_analysis_params(self,
                                                 prompt: str,
                                                 available_columns: List[str]) -> Tuple[Optional[str], Optional[str], bool]:
        # Create OpenAI client
        client = self._get_openai_client()

        # Define the function schema for OpenAI
        tools = [
            {
                "type": "function",
                "function": {
                    "name": "analyze_columns",
                    "description": "Extract column analysis parameters from user prompt",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "selected_columns": {
                                "type": "array",
                                "items": {"type": "string"},
                                "description": "List of column names to analyze (exact names from available columns)"
                            },
                            "group_column": {
                                "type": "string",
                                "description": "Optional column name to group by (exact name from available columns). Use null if no grouping needed."
                            },
                            "columns_are_paired": {
                                "type": "boolean",
                                "description": "True if the selected columns represent paired data that should be analyzed together, False if they are independent variables"
                            }
                        },
                        "required": ["selected_columns", "columns_are_paired"]
                    }
                }
            }
        ]

        # Create the system prompt with available columns
        system_prompt = f"""You are an expert data analyst. The user has a dataset with these columns: {', '.join(available_columns)}.

Based on their request, extract:
1. selected_columns: The exact column names they want to analyze (must match exactly from the available columns)
2. group_column: Optional column to group by (exact name, or null if no grouping)
3. columns_are_paired: Whether columns represent paired data (like before/after measurements) or independent variables

Important rules:
- Only use exact column names from the available list
- If a column is used as group_column, it cannot be in selected_columns
- Paired columns are used for related measurements (before/after, treatment/control, etc.)
- Independent columns are separate variables to compare

Available columns: {', '.join(available_columns)}"""

        # Create the input for OpenAI
        input_list = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": prompt}
        ]

        # Call OpenAI API
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=input_list,
            tools=tools,
            # force the model to use the function
            tool_choice={"type": "function", "function": {"name": "analyze_columns"}}
        )

        # Extract function call result
        if response.choices[0].message.tool_calls:
            tool_call = response.choices[0].message.tool_calls[0]
            if tool_call.function.name == "analyze_columns":
                function_args = json.loads(tool_call.function.arguments)

                selected_columns = function_args.get("selected_columns", [])
                group_column = function_args.get("group_column")
                columns_are_paired = function_args.get("columns_are_paired", False)

                print("Extracted parameters:")
                print(f"Selected columns: {selected_columns}")
                print(f"Group column: {group_column}")
                print(f"Columns are paired: {columns_are_paired}")
                print('--------------------------------')

                # Convert to expected format
                columns_input = ", ".join(selected_columns) if selected_columns else None
                group_input = group_column if group_column else None

                return columns_input, group_input, columns_are_paired

        return None, None, None

    async def validate_and_run_analysis(
            self,
            current_df: DataFrame,
            columns_input: str,
            group_input: Optional[str],
            columns_are_paired: bool):

        if not columns_input.strip():
            return rx.toast.error("Please enter at least one column name.")

        # Split by comma and clean up whitespace
        columns = [col.strip() for col in columns_input.split(",") if col.strip()]

        if not columns:
            return rx.toast.error("No valid columns found.")

        available_columns = list(current_df.columns)

        # Basic validation - check for existence in dataframe
        missing_columns = []
        for col in columns:
            if col not in available_columns:
                missing_columns.append(col)

        # Show validation results for main columns
        if missing_columns:
            return rx.toast.error(
                f"Columns not found in dataframe: '{', '.join(missing_columns)}'. Available columns: '{', '.join(available_columns)}'")

        group_column: Optional[str] = None
        if group_input:
            # Handle group column (optional)
            group_column = group_input.strip()
            columns_are_paired = False  # Force independent if grouping

            # Validate group column if provided
            if group_column not in available_columns:
                return rx.toast.error(
                    f"Group column '{group_column}' not found in dataframe. Available columns: '{', '.join(available_columns)}'")

            # If group column is provided, only allow 1 selected column
            if len(columns) > 1:
                return rx.toast.error(
                    f"When a group column is provided, only 1 column can be selected. You selected {len(columns)} columns: {', '.join(columns)}")

            if group_column in columns:
                return rx.toast.error("Group column cannot be one the selected column.")

        # Check that all selected columns have the same number of non-null rows
        # row_counts = {}
        # for col in valid_columns:
        #     col_data = current_df[col]
        #     non_null_count = col_data.notna().sum()
        #     row_counts[col] = non_null_count

        # # Check if all columns have the same number of rows
        # unique_row_counts = set(row_counts.values())
        # if len(unique_row_counts) > 1:
        #     count_details = ', '.join([f"{col}: {count} rows" for col, count in row_counts.items()])
        #     return rx.toast.error(f"Selected columns have different numbers of non-null rows: {count_details}")

        # Filter and unfold the dataframe if group column is provided
        processed_df = self._get_filtered_and_unfolded_dataframe(
            selected_columns=columns,
            group_column=group_column,
            original_df=current_df
        )

        stats_analyzer = AiTableStats(
            dataframe=processed_df,
            columns_are_independent=not columns_are_paired,
        )

        # Run the statistical analysis decision tree
        stats_analyzer.run_statistical_analysis()

        # Convert test history to JSON for display
        async with self:
            try:
                self.test_history_json = json.dumps(stats_analyzer.test_history, indent=2, default=str)

                # Get the last test result if available
                if stats_analyzer.test_history:
                    self.last_test_json = json.dumps(stats_analyzer.test_history[-1], indent=2, default=str)
                else:
                    self.last_test_json = ""
            except Exception as e:
                self.test_history_json = f"Error serializing test history: {str(e)}"
                self.last_test_json = f"Error serializing last test: {str(e)}"

        success_msg = f"Valid columns found: {', '.join(columns)}"
        if group_column:
            success_msg += f" (grouped by: {group_column})"
        return rx.toast.success(success_msg)

    def _get_filtered_and_unfolded_dataframe(self, selected_columns: list,
                                             group_column: Optional[str],
                                             original_df: DataFrame):
        """
        Filter the dataframe to selected columns + group column, then unfold by group column.

        :param selected_columns: List of selected column names
        :param group_column: Name of the group column to unfold by
        :param original_df: Original dataframe
        :return: Filtered and unfolded DataFrame
        """
        # If no group column, return the filtered dataframe as-is
        if not group_column:
            return original_df[selected_columns]

        # Create columns to include (selected columns + group column)
        columns_to_include = selected_columns.copy()
        if group_column and group_column not in columns_to_include:
            columns_to_include.append(group_column)

        # Filter the dataframe to only include the selected columns and group column
        filtered_df = original_df[columns_to_include]

        # Create a Table from the filtered dataframe
        table = Table(filtered_df)

        # Create unfolder helper and unfold by the group column
        unfolder_helper = TableUnfolderHelper()
        unfolded_table = unfolder_helper.unfold_by_columns(table, [group_column])

        # Return the unfolded dataframe
        return unfolded_table.get_data()

    @rx.event
    def clear_test_results(self):
        """Clear test history and last test results."""
        self.test_history_json = ""
        self.last_test_json = ""
        return rx.toast.info("Test results cleared.")

    def _get_openai_client(self) -> OpenAI:
        """Get OpenAI client with API key"""
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise ValueError("OpenAI API key is not set")
        return OpenAI(api_key=api_key)
