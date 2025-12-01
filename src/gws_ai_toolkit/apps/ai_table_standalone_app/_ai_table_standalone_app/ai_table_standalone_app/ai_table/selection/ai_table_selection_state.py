import pandas as pd
import reflex as rx
from gws_core import Logger, Table

from ..ai_table_data_state import AiTableDataState


class AiTableSelectionState(rx.State):
    """State management for table cell selection and extraction.

    This state class manages cell selection in the AG Grid table,
    handles the extract dialog, and creates new tables from selections.
    """

    # Selection and table management
    current_selection: list[dict] = []
    extract_dialog_open: bool = False
    use_first_row_as_header: bool = False

    @rx.event
    def on_cell_selection_changed(self, selected_cells):
        """Handle cell selection changes in AG Grid"""
        self.current_selection = selected_cells

    @rx.event
    def open_extract_dialog(self):
        """Open the extract dialog"""
        self.extract_dialog_open = True

    @rx.event
    def close_extract_dialog(self):
        """Close the extract dialog"""
        self.extract_dialog_open = False
        self.use_first_row_as_header = False

    @rx.event
    def toggle_first_row_as_header(self):
        """Toggle the first row as header checkbox"""
        self.use_first_row_as_header = not self.use_first_row_as_header

    @rx.event
    async def extract_selection(self):
        """Extract the selected data and create a new subtable"""

        if not self.current_selection or len(self.current_selection) != 1:
            return

        selection = self.current_selection[0]

        # Get data state to access current dataframe and add new table
        data_state = await self.get_state(AiTableDataState)

        # Get the source dataframe from current table
        source_df = data_state.get_current_dataframe()
        table_item = data_state._excel_files.get(data_state.current_table_id)
        source_name = table_item.name if table_item else "table"

        if source_df is None or source_df.empty:
            Logger.error("No valid dataframe available for extraction")
            return

        # Extract row and column ranges
        start_row = selection.get("startRow", 0)
        end_row = selection.get("endRow", 0)
        columns = selection.get("columns", [])

        # Handle inverted selection (when user selects from bottom to top)
        if start_row > end_row:
            start_row, end_row = end_row, start_row

        # Extract the subset of data
        selected_data: pd.DataFrame
        if columns:
            # Select specific columns and rows using iloc for row indexing and column names
            selected_data = source_df.iloc[start_row : end_row + 1][columns]
        else:
            # Select all columns for the row range
            selected_data = source_df.iloc[start_row : end_row + 1]

        # Handle header option
        if self.use_first_row_as_header and not selected_data.empty:
            # Use first row as header
            new_columns = selected_data.iloc[0].values
            selected_data = selected_data.iloc[1:]
            selected_data.columns = new_columns

        # Create subtable filename
        subtable_name = f"{source_name}_subtable"

        # Add new subtable via data state
        new_table = Table(selected_data)
        new_table.name = subtable_name
        data_state.add_table(new_table)

        # Close the dialog
        self.close_extract_dialog()

    @rx.var
    def can_extract(self) -> bool:
        """Check if selection can be extracted"""
        return len(self.current_selection) == 1 and self.current_selection[0] is not None

    @rx.var
    async def selection_info(self) -> str:
        """Get information about current selection"""
        if not self.current_selection or len(self.current_selection) != 1:
            return "No valid selection"

        selection = self.current_selection[0]
        start_row = selection.get("startRow", 0)
        end_row = selection.get("endRow", 0)
        columns = selection.get("columns", [])

        # Handle inverted selection (when user selects from bottom to top)
        if start_row > end_row:
            start_row, end_row = end_row, start_row

        # Get data state to access current dataframe info
        data_state: AiTableDataState = await self.get_state(AiTableDataState)

        row_count = end_row - start_row + 1
        col_count = len(columns) if columns else data_state.nb_columns

        return f"Selected: {row_count} rows, {col_count} columns"
