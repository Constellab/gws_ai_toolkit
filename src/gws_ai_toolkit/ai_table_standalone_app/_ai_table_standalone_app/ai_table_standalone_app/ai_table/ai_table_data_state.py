import os
import uuid
from typing import Dict, List, Literal, Optional

import pandas as pd
import reflex as rx
from gws_core import File, Logger, Table

from gws_ai_toolkit.core.table_item import TableItem

ORIGINAL_TABLE_ID = "original"

RightPanelState = Literal["closed", "chat", "stats"]
ChatMode = Literal["plot", "transform"]


class AiTableDataState(rx.State):
    """State management for AI Table dataframe and table display.

    This state class manages dataframe loading, sheet selection, and table display
    for the AI Table. It handles loading files from resources (not file upload)
    and provides data for the table visualization.
    """

    # Current dataframe management (serializable)
    current_sheet_name: str = ""
    current_file_path: str = ""
    current_file_name: str = ""

    # UI state
    right_panel_state: RightPanelState = "closed"
    current_chat_mode: ChatMode = "plot"

    # Table
    _tables: Dict[str, TableItem] = {}
    current_table_id: str = ORIGINAL_TABLE_ID  # Default to original table

    # Selection and table management
    current_selection: List[dict] = []
    extract_dialog_open: bool = False
    use_first_row_as_header: bool = False

    def get_current_dataframe_item(self) -> Optional[TableItem]:
        """Create DataFrameItem from current file info"""
        return self._tables.get(self.current_table_id)

    def get_current_table(self) -> Optional[Table]:
        """Get the current active table (original or subtable)"""
        table_item = self.get_current_dataframe_item()
        if table_item:
            return table_item.get_table(self.current_sheet_name)
        return None

    def get_current_dataframe(self) -> Optional[pd.DataFrame]:
        """Get the current active dataframe (original or subtable)"""
        # Get dataframe item for current table
        table_item = self.get_current_dataframe_item()
        if table_item:
            return table_item.get_dataframe(self.current_sheet_name)
        return None

    def set_resource(self, file: File, name: Optional[str] = None):
        """Set the resource file to load data from

        Args:
            file (File): File to set
            name (Optional[str]): Optional name to use instead of extracting from file path
        """

        self.current_file_path = file.path
        # Use provided name or extract from file path as fallback
        self.current_file_name = name or os.path.splitext(os.path.basename(file.path))[0]

        # Add original table to the tables dictionary
        table_item = TableItem.from_file(
            f"{self.current_file_name}",
            self.current_file_path
        )
        self._tables[ORIGINAL_TABLE_ID] = table_item

        # Set current table to original
        self.current_table_id = ORIGINAL_TABLE_ID

    @rx.event
    def switch_sheet(self, sheet_name: str):
        """Switch to a different sheet in the current dataframe"""
        df_item = self.get_current_dataframe_item()
        if df_item and sheet_name in df_item.get_sheet_names():
            self.current_sheet_name = sheet_name

    @rx.event
    def toggle_right_panel_state(self, state: RightPanelState):
        """Set the right panel state (chat, stats, closed)"""
        if self.right_panel_state == state:
            self.right_panel_state = "closed"
        else:
            self.right_panel_state = state

    @rx.event
    def set_chat_mode(self, mode: ChatMode):
        """Set the current chat mode (plot, transform)"""
        self.current_chat_mode = mode

    @rx.var
    def right_panel_opened(self) -> bool:
        """Check if right panel is open"""
        return self.right_panel_state != "closed"

    @rx.var
    def get_sheet_names(self) -> List[str]:
        """Get sheet names for the current dataframe"""
        df_item = self.get_current_dataframe_item()
        if df_item:
            return df_item.get_sheet_names()
        return []

    @rx.var
    def dataframe_loaded(self) -> bool:
        """Check if dataframe is loaded"""
        return bool(self.current_file_path and os.path.exists(self.current_file_path))

    @rx.var
    def nb_rows(self) -> int:
        """Get the number of rows in the current data"""
        current_df = self.get_current_dataframe()
        return current_df.shape[0] if current_df is not None and not current_df.empty else 0

    @rx.var
    def nb_columns(self) -> int:
        """Get the number of columns in the current data"""
        current_df = self.get_current_dataframe()
        return current_df.shape[1] if current_df is not None and not current_df.empty else 0

    @rx.var
    def ag_grid_column_defs(self) -> List[dict]:
        """Get column definitions for AG Grid"""
        current_df = self.get_current_dataframe()
        if current_df is None or current_df.empty:
            return []

        column_defs = []
        for col in current_df.columns:
            column_defs.append({
                "field": str(col),
                "headerName": str(col),
                "sortable": True,
                "filter": True,
                "resizable": True
            })

        return column_defs

    @rx.var
    def ag_grid_row_data(self) -> List[dict]:
        """Get row data for AG Grid as list of dictionaries"""
        current_df = self.get_current_dataframe()
        if current_df is None or current_df.empty:
            return []

        # Convert DataFrame to list of dictionaries (rows)
        row_data = []
        for _, row in current_df.iterrows():
            row_dict = {}
            for col in current_df.columns:
                value = row[col]
                # Convert to string for display, handle NaN values
                if pd.isna(value):
                    row_dict[str(col)] = ""
                else:
                    row_dict[str(col)] = str(value)
            row_data.append(row_dict)

        return row_data

    @rx.var
    def has_multiple_sheets(self) -> bool:
        """Check if current file has multiple sheets"""
        df_item = self.get_current_dataframe_item()
        return df_item.has_multiple_sheets() if df_item else False

    # Selection and extraction methods
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
    def extract_selection(self):
        """Extract the selected data and create a new subtable"""
        if not self.current_selection or len(self.current_selection) != 1:
            return

        selection = self.current_selection[0]

        # Get the source dataframe (original or current table)
        source_df = self.get_current_dataframe()
        if self.current_table_id == ORIGINAL_TABLE_ID:
            source_name = self.current_file_name
        else:
            table_item = self._tables.get(self.current_table_id)
            source_name = table_item.name if table_item else "table"

        if source_df is None or source_df.empty:
            Logger.error("No valid dataframe available for extraction")
            return

        # Extract row and column ranges
        start_row = selection.get('startRow', 0)
        end_row = selection.get('endRow', 0)
        columns = selection.get('columns', [])

        # Extract the subset of data
        selected_data: pd.DataFrame
        if columns:
            # Select specific columns and rows
            selected_data = source_df.loc[start_row:end_row, columns]
        else:
            # Select all columns for the row range
            selected_data = source_df.iloc[start_row:end_row + 1]

        # Handle header option
        if self.use_first_row_as_header and not selected_data.empty:
            # Use first row as header
            new_columns = selected_data.iloc[0].values
            selected_data = selected_data.iloc[1:]
            selected_data.columns = new_columns

        # Create subtable filename
        subtable_name = f"{source_name}_subtable"

        # Add new subtable
        new_table = Table(selected_data)
        self.set_current_table(new_table, subtable_name)

        # Close the dialog
        self.close_extract_dialog()

    @rx.event
    def switch_to_original(self):
        """Switch back to original table"""
        self.current_table_id = ORIGINAL_TABLE_ID

    @rx.event
    def switch_to_subtable(self, table_id: str):
        """Switch to a specific table"""
        if table_id == ORIGINAL_TABLE_ID or table_id in self._tables:
            self.current_table_id = table_id

    @rx.event
    def switch_table(self, table_id: str):
        """Switch to original table or a specific table based on ID"""
        if table_id == ORIGINAL_TABLE_ID or table_id in self._tables:
            self.current_table_id = table_id

    @rx.event
    def remove_current_table(self):
        """Remove a subtable"""
        # Don't allow removing the original table
        if self.current_table_id == ORIGINAL_TABLE_ID:
            return

        table_item = self._tables.get(self.current_table_id)
        if table_item:
            # Remove from dictionary
            del self._tables[self.current_table_id]
            # Switch to original if this was the current table
            if self.current_table_id == self.current_table_id:
                self.current_table_id = ORIGINAL_TABLE_ID

    @rx.var
    def can_extract(self) -> bool:
        """Check if selection can be extracted"""
        return len(self.current_selection) == 1 and self.current_selection[0] is not None

    @rx.var
    def selection_info(self) -> str:
        """Get information about current selection"""
        if not self.current_selection or len(self.current_selection) != 1:
            return "No valid selection"

        selection = self.current_selection[0]
        start_row = selection.get('startRow', 0)
        end_row = selection.get('endRow', 0)
        columns = selection.get('columns', [])

        row_count = end_row - start_row + 1
        col_count = len(columns) if columns else self.nb_columns

        return f"Selected: {row_count} rows, {col_count} columns"

    @rx.var
    def current_table_name(self) -> str:
        """Get the name of the currently active table"""
        if self.current_table_id == ORIGINAL_TABLE_ID:
            return f"{self.current_file_name}"
        else:
            table_item = self._tables.get(self.current_table_id)
            return table_item.name if table_item else "Unknown Table"

    @rx.var
    def subtables_list(self) -> List[Dict[str, str]]:
        """Get list of subtables (excluding original) for UI iteration"""
        subtables = []
        for table_id, table_item in self._tables.items():
            if table_id != ORIGINAL_TABLE_ID:
                subtables.append({
                    "id": table_id,
                    "name": table_item.name
                })
        return subtables

    def set_current_table(self, table: Table, name: str) -> None:
        """Set a transformed DataFrame as the current active DataFrame

        Args:
            transformed_df: The transformed DataFrame to set as current
        """
        # Create new table entry for the transformed data
        table_id = f"transformed_{uuid.uuid4()}"
        self._tables[table_id] = TableItem.from_table(name, table)
        self.current_table_id = table_id
