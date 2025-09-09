
import json

import reflex as rx

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
        columns_input = form_data.get("columns_input", "")
        columns_are_paired = form_data.get("columns_are_paired", False)

        if not columns_input.strip():
            return rx.toast.error("Please enter at least one column name.")

        # Split by comma and clean up whitespace
        columns = [col.strip() for col in columns_input.split(",") if col.strip()]

        if not columns:
            return rx.toast.error("No valid columns found.")

        # Get current dataframe from AiTableDataState
        try:
            ai_table_state = await self.get_state(AiTableDataState)
            current_df = ai_table_state.current_dataframe

            if current_df is None or current_df.empty:
                return rx.toast.error("No dataframe available. Please load a file first.")

            available_columns = list(current_df.columns)
        except Exception as e:
            return rx.toast.error(f"Error accessing dataframe: {str(e)}")

        # Basic validation - check for valid column names and existence in dataframe
        valid_columns = []
        missing_columns = []

        for col in columns:
            if col not in available_columns:
                missing_columns.append(col)
            else:
                valid_columns.append(col)

        # Show validation results

        if missing_columns:
            return rx.toast.error(
                f"Columns not found in dataframe: '{', '.join(missing_columns)}'. Available columns: '{', '.join(available_columns)}'")

        # Check that all selected columns have the same number of non-null rows
        row_counts = {}
        for col in valid_columns:
            col_data = current_df[col]
            non_null_count = col_data.notna().sum()
            row_counts[col] = non_null_count

        # # Check if all columns have the same number of rows
        # unique_row_counts = set(row_counts.values())
        # if len(unique_row_counts) > 1:
        #     count_details = ', '.join([f"{col}: {count} rows" for col, count in row_counts.items()])
        #     return rx.toast.error(f"Selected columns have different numbers of non-null rows: {count_details}")

        # Use the checkbox value to determine if columns are independent
        # If columns are paired, they are not independent
        columns_are_independent = not columns_are_paired

        # Filter the dataframe to only include the selected columns
        filtered_df = current_df[valid_columns]

        stats_analyzer = AiTableStats(
            dataframe=filtered_df,
            columns_are_independent=columns_are_independent
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

        return rx.toast.success(f"Valid columns found: {', '.join(valid_columns)}")

    @rx.event
    def clear_test_results(self):
        """Clear test history and last test results."""
        self.test_history_json = ""
        self.last_test_json = ""
        return rx.toast.info("Test results cleared.")
