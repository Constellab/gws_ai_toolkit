import os
import tempfile
import uuid
from typing import Dict, List, Optional

import pandas as pd
import reflex as rx
from gws_core import File, Logger, ResourceModel

from .dataframe_item import DataFrameItem

ORIGINAL_TABLE_ID = "original"


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
    chat_panel_open: bool = False

    # Table
    _tables: Dict[str, DataFrameItem] = {}  # Dict with ID as key: DataFrameItem
    current_table_id: str = ORIGINAL_TABLE_ID  # Default to original table

    # Selection and table management
    current_selection: List[dict] = []
    extract_dialog_open: bool = False
    use_first_row_as_header: bool = False

    def _get_current_dataframe_item(self) -> Optional[DataFrameItem]:
        """Create DataFrameItem from current file info"""
        if not self.current_file_path or not os.path.exists(self.current_file_path):
            return None
        return DataFrameItem(self.current_file_name, self.current_file_path)

    def _get_table_dataframe_item_by_id(self, table_id: str) -> Optional[DataFrameItem]:
        """Get DataFrameItem for a table by ID"""
        if table_id == ORIGINAL_TABLE_ID:
            return self._get_current_dataframe_item()

        return self._tables.get(table_id)

    def set_resource(self, resource: ResourceModel):
        """Set the resource to analyze and load it as dataframe

        Args:
            resource (ResourceModel): Resource model to set
        """
        file = resource.get_resource()
        if not isinstance(file, File) or not file.is_csv_or_excel():
            Logger.error("Resource is not a valid CSV or Excel file")
            return

        self.current_file_path = file.path
        self.current_file_name = os.path.splitext(os.path.basename(file.path))[0]

        # Test if file can be loaded
        df_item = self._get_current_dataframe_item()
        if df_item:
            test_df = df_item.get_default_dataframe()
            if test_df.empty:
                Logger.error(f"The dataframe is empty: {file.path}")
                return

            # Set default sheet for Excel files
            if df_item.get_sheet_names():
                self.current_sheet_name = df_item.get_sheet_names()[0]
            else:
                self.current_sheet_name = ""

            # Add original table to the tables dictionary
            self._tables[ORIGINAL_TABLE_ID] = DataFrameItem(
                f"{self.current_file_name} (Original)",
                self.current_file_path
            )

            # Set current table to original
            self.current_table_id = ORIGINAL_TABLE_ID

    @rx.event
    def switch_sheet(self, sheet_name: str):
        """Switch to a different sheet in the current dataframe"""
        df_item = self._get_current_dataframe_item()
        if df_item and sheet_name in df_item.get_sheet_names():
            self.current_sheet_name = sheet_name

    @rx.event
    def toggle_chat_panel(self):
        """Toggle the chat panel visibility"""
        self.chat_panel_open = not self.chat_panel_open

    @rx.var
    def get_sheet_names(self) -> List[str]:
        """Get sheet names for the current dataframe"""
        df_item = self._get_current_dataframe_item()
        if df_item:
            return df_item.get_sheet_names()
        return []

    @rx.var
    def current_dataframe(self) -> Optional[pd.DataFrame]:
        """Get the current active dataframe (original or subtable)"""
        # Get dataframe item for current table
        table_item = self._get_table_dataframe_item_by_id(self.current_table_id)
        if table_item:
            # For original table, respect sheet selection
            if self.current_table_id == ORIGINAL_TABLE_ID and self.current_sheet_name:
                return table_item.get_dataframe(self.current_sheet_name)
            else:
                return table_item.get_default_dataframe()
        return None

    @rx.var
    def dataframe_loaded(self) -> bool:
        """Check if dataframe is loaded"""
        return bool(self.current_file_path and os.path.exists(self.current_file_path))

    @rx.var
    def nb_rows(self) -> int:
        """Get the number of rows in the current data"""
        current_df = self.current_dataframe
        return current_df.shape[0] if current_df is not None and not current_df.empty else 0

    @rx.var
    def nb_columns(self) -> int:
        """Get the number of columns in the current data"""
        current_df = self.current_dataframe
        return current_df.shape[1] if current_df is not None and not current_df.empty else 0

    @rx.var
    def ag_grid_column_defs(self) -> List[dict]:
        """Get column definitions for AG Grid"""
        current_df = self.current_dataframe
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
        current_df = self.current_dataframe
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

    def get_current_dataframe_item(self) -> Optional[DataFrameItem]:
        """Get the current dataframe item for chat integration"""
        return self._get_current_dataframe_item()

    @rx.var
    def has_multiple_sheets(self) -> bool:
        """Check if current file has multiple sheets"""
        df_item = self._get_current_dataframe_item()
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
        source_df = self.current_dataframe
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

        # Create temporary file with extraction data
        with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False, prefix=f"{subtable_name}_") as temp_file:
            selected_data.to_csv(temp_file.name, index=False)
            temp_file_path = temp_file.name

        # Create new table entry
        table_id = str(uuid.uuid4())
        self._tables[table_id] = DataFrameItem(subtable_name, temp_file_path)
        self.current_table_id = table_id

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
    def remove_subtable(self, table_id: str):
        """Remove a subtable"""
        # Don't allow removing the original table
        if table_id == ORIGINAL_TABLE_ID:
            return

        table_item = self._tables.get(table_id)
        if table_item:
            # Remove from dictionary
            del self._tables[table_id]
            # Switch to original if this was the current table
            if self.current_table_id == table_id:
                self.current_table_id = ORIGINAL_TABLE_ID
            # Clean up temp file
            if os.path.exists(table_item.file_path):
                os.unlink(table_item.file_path)

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
            return f"{self.current_file_name} (Original)"
        else:
            table_item = self._tables.get(self.current_table_id)
            return table_item.name if table_item else "Unknown Table"

    @rx.var
    def tables(self) -> Dict[str, Dict[str, str]]:
        """Public property to access tables data for UI - returns dict format for compatibility"""
        result = {}
        for table_id, table_item in self._tables.items():
            result[table_id] = {
                "name": table_item.name,
                "file_path": table_item.file_path
            }
        return result

    @rx.var
    def subtables_list(self) -> List[Dict[str, str]]:
        """Get list of subtables (excluding original) for UI iteration"""
        subtables = []
        for table_id, table_item in self._tables.items():
            if table_id != ORIGINAL_TABLE_ID:
                subtables.append({
                    "id": table_id,
                    "name": table_item.name,
                    "file_path": table_item.file_path
                })
        return subtables
