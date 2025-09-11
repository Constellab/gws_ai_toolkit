
import json
import os
from typing import List, Optional, cast

import reflex as rx
from gws_core import BaseModelDTO, Table, TableUnfolderHelper
from openai import OpenAI
from pandas import DataFrame

from ..ai_table_data_state import AiTableDataState
from .ai_table_stats_class import AiTableStats
from .ai_table_stats_type import AiTableStatsResults, AiTableStatsTestName


class AiTableStatsRunConfig(BaseModelDTO):
    ai_prompt: str
    columns: List[str]
    str_columns: str  # Comma-separated string of columns for display
    group_input: Optional[str]
    columns_are_paired: bool


class AiTableStatsState(rx.State):
    """State for the AI Table stats component."""

    is_processing: bool = False
    _current_stats_analyzer: Optional[AiTableStats] = None

    last_run_config: Optional[AiTableStatsRunConfig] = None

    @rx.event(background=True)  # type: ignore
    async def process_ai_prompt(self, form_data: dict):
        if self.is_processing:
            return rx.toast.error("Analysis already in progress. Please wait.")

        current_df: DataFrame | None
        async with self:
            self.clear_test_results()

            prompt = form_data.get("ai_prompt", "").strip()
            if not prompt:
                return rx.toast.error("Please enter a prompt describing your analysis.")

                # Get current dataframe to extract column names
            ai_table_state = await self.get_state(AiTableDataState)
            current_df = ai_table_state.current_dataframe

            if current_df is None or current_df.empty:
                return rx.toast.error("No dataframe available. Please load a file first.")

            self.is_processing = True

        try:
            available_columns = list(current_df.columns)

            # Convert prompt to analysis parameters using OpenAI
            last_run_config = await self._convert_prompt_to_analysis_params(
                prompt=prompt,
                available_columns=available_columns
            )

            if not last_run_config.columns:
                return rx.toast.error(
                    "Could not extract valid column names from the prompt. "
                    "Please check your prompt and ensure you reference existing column names.")

            async with self:
                self.last_run_config = last_run_config

            # Call the validation and analysis function
            return await self.validate_and_run_analysis(
                current_df=current_df,
                columns=last_run_config.columns,
                group_input=last_run_config.group_input,
                columns_are_paired=last_run_config.columns_are_paired
            )
        finally:
            async with self:
                self.is_processing = False

    async def _convert_prompt_to_analysis_params(self,
                                                 prompt: str,
                                                 available_columns: List[str]) -> AiTableStatsRunConfig:
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

                return AiTableStatsRunConfig(
                    ai_prompt=prompt,
                    columns=selected_columns,
                    str_columns=", ".join(selected_columns),
                    group_input=function_args.get("group_column"),
                    columns_are_paired=function_args.get("columns_are_paired", False),
                )

        return AiTableStatsRunConfig(
            ai_prompt=prompt,
            columns=[],
            str_columns="",
            group_input=None,
            columns_are_paired=False,
        )

    async def validate_and_run_analysis(
            self,
            current_df: DataFrame,
            columns: List[str],
            group_input: Optional[str],
            columns_are_paired: bool):

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

            if group_column in columns:
                # remove the group column from selected columns if present
                columns.remove(group_column)

            # Validate group column if provided
            if group_column not in available_columns:
                return rx.toast.error(
                    f"Group column '{group_column}' not found in dataframe. Available columns: '{', '.join(available_columns)}'")

            # If group column is provided, only allow 1 selected column
            if len(columns) > 1:
                return rx.toast.error(
                    f"When a group column is provided, only 1 column can be selected. You selected {len(columns)} columns: {', '.join(columns)}")

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

        # Store test history and current stats analyzer
        async with self:
            self._current_stats_analyzer = stats_analyzer

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

    @rx.var
    def test_history(self) -> List[AiTableStatsResults]:
        """Get the test history."""
        if not self._current_stats_analyzer:
            return []
        return self._current_stats_analyzer.test_history

    @rx.var
    def last_test_result(self) -> Optional[AiTableStatsResults]:
        """Get the last test result."""
        # Get the last test result if available
        if self.test_history:
            return self.test_history[-1]
        else:
            return None

    @rx.var
    def suggested_additional_test(self) -> Optional[str]:
        """Get suggested additional test if any."""
        if self._current_stats_analyzer:
            return self._current_stats_analyzer.suggested_additional_tests()
        return None

    @rx.var
    def has_suggested_additional_test(self) -> bool:
        """Check if there's a suggested additional test."""
        return self.suggested_additional_test is not None

    @rx.event
    def clear_test_results(self):
        """Clear test history and last test results."""
        self._current_stats_analyzer = None
        self.last_run_config = None

    @rx.event(background=True)  # type: ignore
    async def run_additional_test(self, test_name: str):
        """Run an additional statistical test."""
        if self.is_processing:
            return rx.toast.error("Analysis already in progress. Please wait.")

        if not self._current_stats_analyzer:
            return rx.toast.error("No statistical analysis available. Please run an analysis first.")

        async with self:
            self.is_processing = True

        try:
            # Run other additional tests normally (without reference column)
            self._current_stats_analyzer.run_additional_test(cast(AiTableStatsTestName, test_name))

        finally:
            async with self:
                self.is_processing = False
                self._current_stats_analyzer = self._current_stats_analyzer  # Trigger state update

    @rx.event(background=True)  # type: ignore
    async def run_additional_test_with_reference_column(self, form_data: dict):
        """Run additional test with reference column from form."""
        if self.is_processing:
            return rx.toast.error("Analysis already in progress. Please wait.")

        if not self._current_stats_analyzer or not self.last_run_config:
            return rx.toast.error("No statistical analysis available. Please run an analysis first.")

        # Get reference column/group from form
        reference_input: str = form_data.get("reference_column", "").strip()

        # Compute actual reference column name based on group_input
        reference_column: str | None = None
        if reference_input:
            if self.last_run_config.group_input:
                # For grouped data: format as 'COLUMN_GROUP'
                first_column = self.last_run_config.columns[0] if self.last_run_config.columns else ""
                reference_column = f"{first_column}_{reference_input}"

                # Use AiTableStats methods to validate column existence
                if not self._current_stats_analyzer.has_column(reference_column):
                    return rx.toast.error(
                        f"Reference group '{reference_input}' not found in the column '{self.last_run_config.group_input}'.")

            else:
                # For non-grouped data: use input as column name directly
                reference_column = reference_input

                # Use AiTableStats methods to validate column existence
                if not self._current_stats_analyzer.has_column(reference_column):
                    return rx.toast.error(
                        f"Reference column '{reference_column}' not found in dataframe or is not a selected column.")

        async with self:
            self.is_processing = True

        try:
            # Run pairwise test with reference column
            self._current_stats_analyzer.run_student_independent_pairwise(reference_column)

        finally:
            async with self:
                self.is_processing = False
                self._current_stats_analyzer = self._current_stats_analyzer  # Trigger state update

    def _get_openai_client(self) -> OpenAI:
        """Get OpenAI client with API key"""
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise ValueError("OpenAI API key is not set")
        return OpenAI(api_key=api_key)
