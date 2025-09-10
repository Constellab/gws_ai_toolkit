
import json
from typing import Optional

import reflex as rx
from gws_core import Table, TableUnfolderHelper
from pandas import DataFrame

from ..ai_table_data_state import AiTableDataState
# Create AiTableStats instance and run analysis
from .ai_table_stats_class import AiTableStats


class AiTableStatsState(rx.State):
    """State for the AI Table stats component."""

    test_history_json: str = ""
    last_test_json: str = ""

    @rx.event
    async def submit_columns(self, form_data: dict):
        """Submit and validate column names."""
        columns_input: str = form_data.get("columns_input", "")
        group_input: str = form_data.get("group_input", "")
        columns_are_paired: bool = form_data.get("columns_are_paired", False)

        if not columns_input.strip():
            return rx.toast.error("Please enter at least one column name.")

        # Split by comma and clean up whitespace
        columns = [col.strip() for col in columns_input.split(",") if col.strip()]

        if not columns:
            return rx.toast.error("No valid columns found.")

        # Get current dataframe from AiTableDataState
        ai_table_state = await self.get_state(AiTableDataState)
        current_df = ai_table_state.current_dataframe

        if current_df is None or current_df.empty:
            return rx.toast.error("No dataframe available. Please load a file first.")

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
