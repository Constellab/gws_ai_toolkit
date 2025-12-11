import reflex as rx
from gws_ai_toolkit.tasks.table_subtable_selector import TableSubtableSelector
from gws_core import Logger

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
        """Extract the selected data and create a new subtable using TableSubtableSelector task"""

        if not self.current_selection or len(self.current_selection) != 1:
            return

        selection = self.current_selection[0]

        # Get data state to access current dataframe and add new table
        data_state = await self.get_state(AiTableDataState)

        # Get the source table
        excel_file = data_state._excel_files.get(data_state.current_table_id)
        if not excel_file:
            Logger.error("No valid table available for extraction")
            return

        source_table = excel_file.get_table(data_state.current_sheet_name)
        source_name = excel_file.name

        # Extract row and column ranges from selection
        start_row = selection.get("startRow", 0)
        end_row = selection.get("endRow", 0)
        columns = list(selection.get("columns", []))

        # Use TableSubtableSelector task to extract the subtable
        try:
            subtable = TableSubtableSelector.select_subtable(
                source_table=source_table,
                start_row=start_row,
                end_row=end_row,
                columns=columns if columns else None,
                use_first_row_as_header=self.use_first_row_as_header,
            )

            # Set the subtable name
            subtable_name = f"{source_name}_subtable"
            subtable.name = subtable_name

            # Add new subtable via data state
            data_state.add_table(subtable)

            # Close the dialog
            self.close_extract_dialog()

        except Exception as e:
            Logger.error(f"Failed to extract subtable: {e}")
            return

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
