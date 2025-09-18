import uuid
from typing import Dict, List, Literal, Optional

import pandas as pd
import reflex as rx
from gws_core import File, Table

from gws_ai_toolkit.core.table_item import TableItem

RightPanelState = Literal["closed", "chat", "stats"]


class AiTableDataState(rx.State):
    """State management for AI Table dataframe and table display.

    This state class manages dataframe loading, sheet selection, and table display
    for the AI Table. It handles loading files from resources (not file upload)
    and provides data for the table visualization.
    """

    # Current dataframe management (serializable)
    current_sheet_name: str = ""

    # UI state
    right_panel_state: RightPanelState = "closed"

    # Table
    _tables: Dict[str, TableItem] = {}
    current_table_id: str = ""  # Current active table ID


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
        return self.get_current_dataframe() is not None

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


    @rx.event
    def switch_table(self, table_id: str):
        """Switch to a specific table based on ID"""
        if table_id in self._tables:
            self.current_table_id = table_id

    @rx.event
    def remove_current_table(self):
        """Remove the current table"""
        if self.current_table_id and self.current_table_id in self._tables:
            # Remove from dictionary
            del self._tables[self.current_table_id]
            # Switch to the first available table or empty if no tables
            if self._tables:
                self.current_table_id = next(iter(self._tables.keys()))
            else:
                self.current_table_id = ""


    @rx.var
    def current_table_name(self) -> str:
        """Get the name of the currently active table"""
        table_item = self._tables.get(self.current_table_id)
        return table_item.name if table_item else "No Table Selected"

    @rx.var
    def tables_list(self) -> List[Dict[str, str]]:
        """Get list of all tables for UI iteration"""
        tables = []
        for table_id, table_item in self._tables.items():
            tables.append({
                "id": table_id,
                "name": table_item.name
            })
        return tables

    def add_file(self, file: File, name: Optional[str] = None):
        """Set the resource file to load data from

        Args:
            file (File): File to set
            name (Optional[str]): Optional name to use instead of extracting from file path
        """

        table_item = TableItem.from_file(
            name or file.name,
            file.path
        )

        self.add_table(table_item.get_table(), table_item.name)

    def add_table(self, table: Table, name: str) -> None:
        """Set a transformed DataFrame as the current active DataFrame

        Args:
            transformed_df: The transformed DataFrame to set as current
        """
        # Create new table entry for the transformed data
        table_id = f"{uuid.uuid4()}"
        self._tables[table_id] = TableItem.from_table(name, table)
        self.current_table_id = table_id

    def count_tables(self) -> int:
        """Count the number of tables currently loaded"""
        return len(self._tables)
