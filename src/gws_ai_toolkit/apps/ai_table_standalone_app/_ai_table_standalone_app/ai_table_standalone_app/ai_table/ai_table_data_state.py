import uuid
from typing import Literal

import pandas as pd
import reflex as rx
from gws_ai_toolkit.core.excel_file import ExcelFile, ExcelFileDTO, ExcelSheetDTO
from gws_core import File, ResourceModel, Table, Utils

RightPanelState = Literal["closed", "chat", "stats"]
ColumnSizeMode = Literal["default", "dense"]


class AiTableDataState(rx.State):
    """State management for AI Table dataframe and table display.

    This state class manages dataframe loading, sheet selection, and table display
    for the AI Table. It handles loading files from resources (not file upload)
    and provides data for the table visualization.
    """

    # UI state
    right_panel_state: RightPanelState = "closed"
    zoom_level: float = 1.0  # 1.0 = 100%, 0.3 = 30%, etc.
    column_size_mode: ColumnSizeMode = "default"  # default = autoSize on columns, dense = ag_grid_auto_size_strategy, fixed = fixed widths

    # Table
    _excel_files: dict[str, ExcelFile] = {}
    current_table_id: str = ""  # Current active table ID

    # Current dataframe management (serializable)
    current_sheet_name: str = ""

    def get_current_dataframe_item(self) -> ExcelFile | None:
        """Create DataFrameItem from current file info"""
        return self._excel_files.get(self.current_table_id)

    def get_current_table(self) -> ExcelSheetDTO | None:
        """Get the current active table (original or subtable)"""
        table_item = self.get_current_dataframe_item()
        if table_item:
            return table_item.get_table_dto(self.current_sheet_name)
        return None

    def get_current_dataframe(self) -> pd.DataFrame | None:
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

    @rx.event
    def set_zoom(self, zoom: float):
        """Set zoom level to specific value"""
        self.zoom_level = max(0.1, min(3.0, zoom))  # Clamp between 10% and 300%

    @rx.event
    def zoom_in(self):
        """Increase zoom by 10%"""
        self.zoom_level = min(3.0, self.zoom_level + 0.1)

    @rx.event
    def zoom_out(self):
        """Decrease zoom by 10%"""
        self.zoom_level = max(0.1, self.zoom_level - 0.1)

    @rx.event
    def set_column_size_default(self):
        """Set column size to default mode (autoSize on columns)"""
        self.column_size_mode = "default"

    @rx.event
    def set_column_size_dense(self):
        """Set column size to dense mode (ag_grid_auto_size_strategy)"""
        self.column_size_mode = "dense"

    @rx.var
    def right_panel_opened(self) -> bool:
        """Check if right panel is open"""
        return self.right_panel_state != "closed"

    @rx.var
    def get_sheet_names(self) -> list[str]:
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
    def ag_grid_auto_size_strategy(self) -> dict | None:
        """Get auto size strategy for AG Grid based on mode"""
        if self.column_size_mode == "dense":
            return {
                "type": "fitCellContents",
                "skipHeader": True,
                "columnLimits": [{"key": None, "minWidth": 50, "maxWidth": 300}],
            }
        return None

    @rx.var
    def ag_grid_column_defs(self) -> list[dict]:
        """Get column definitions for AG Grid"""
        current_df = self.get_current_dataframe()
        if current_df is None or current_df.empty:
            return []

        column_defs = []
        for col in current_df.columns:
            is_numeric = pd.api.types.is_numeric_dtype(current_df[col])

            col_def = {
                "field": str(col),
                "headerName": str(col),
                "headerTooltip": str(col),  # Show full column name on hover
                "resizable": True,
                "sortable": True,
                "filter": True,
            }

            # Add width or autoSize based on mode
            if self.column_size_mode == "default":
                # Default mode: use autoSize on each column
                col_def["autoSize"] = True
            elif self.column_size_mode == "dense":
                # Dense mode: set initial width so ag_grid_auto_size_strategy applies to all columns
                col_def["width"] = 80 if is_numeric else 120
                col_def["headerClass"] = "dense-header"  # Custom CSS class for styling

            column_defs.append(col_def)

        return column_defs

    @rx.var
    def ag_grid_row_data(self) -> list[dict]:
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
    def select_excel_file(self, excel_file_id: str):
        """Switch to a specific table based on ID"""
        if excel_file_id in self._excel_files:
            self.current_table_id = excel_file_id
            self.current_sheet_name = ""

    @rx.event
    def select_table(self, table_id: str):
        """Switch to a specific table and sheet based on IDs"""
        for key, table in self._excel_files.items():
            sheet_name = table.get_sheet_name_from_id(table_id)
            if sheet_name is not None:
                self.current_table_id = key
                self.current_sheet_name = sheet_name
                return

    @rx.event
    def remove_current_table(self):
        """Remove the current table"""
        if self.current_table_id and self.current_table_id in self._excel_files:
            # Remove from dictionary
            del self._excel_files[self.current_table_id]
            # Switch to the first available table or empty if no tables
            if self._excel_files:
                self.current_table_id = next(iter(self._excel_files.keys()))
            else:
                self.current_table_id = ""

    @rx.var
    def current_table_name(self) -> str:
        """Get the name of the currently active table"""
        table_item = self._excel_files.get(self.current_table_id)
        return table_item.name if table_item else "No Table Selected"

    @rx.var
    def excel_file_list(self) -> list[dict[str, str]]:
        """Get list of all tables for UI iteration"""
        tables = []
        for table_id, table_item in self._excel_files.items():
            tables.append({"id": table_id, "name": table_item.name})
        return tables

    @rx.var
    def all_table_items(self) -> list[ExcelFileDTO]:
        """Get list of all TableItems as DTOs for UI iteration"""
        table_dtos = []
        for table_item in self._excel_files.values():
            table_dtos.append(table_item.to_dto())
        return table_dtos

    def add_file(self, file: File, name: str | None = None, resource_model_id: str | None = None):
        """Set the resource file to load data from

        Args:
            file (File): File to set
            name (Optional[str]): Optional name to use instead of extracting from file path
        """

        existing_names = {table.name for table in self._excel_files.values()}
        new_name = name or file.name or "table"

        # Ensure unique name
        new_unique_name = Utils.generate_unique_str_for_list(list(existing_names), new_name)

        table_item = ExcelFile.from_file(
            id_=str(uuid.uuid4()),
            name=new_unique_name,
            file_path=file.path,
            resource_model_id=resource_model_id,
        )

        self.add_excel_file(table_item)

    def add_table(self, table: Table) -> ExcelSheetDTO:
        """Set a transformed DataFrame as the current active DataFrame

        Args:
            transformed_df: The transformed DataFrame to set as current
        """
        # Create new table entry for the transformed data
        return self.add_excel_file(ExcelFile.from_table(table=table))

    def add_excel_file(self, excel_file: ExcelFile) -> ExcelSheetDTO:
        """Add a TableItem directly to the tables list

        Args:
            table_item (TableItem): TableItem to add
        """
        self._excel_files[excel_file.id] = excel_file
        self.current_table_id = excel_file.id
        return excel_file.get_table_dto()

    def add_resource_model(self, resource_model_id: str):
        resource_model = ResourceModel.get_by_id(resource_model_id)
        if not resource_model:
            raise ValueError(f"Resource with id {resource_model_id} not found")

        resource = resource_model.get_resource()
        if not isinstance(resource, Table):
            raise ValueError(f"Resource with id {resource_model_id} is not a Table resource")

        self.add_table(resource)

    def count_tables(self) -> int:
        """Count the number of tables currently loaded"""
        return len(self._excel_files)

    def get_table(self, table_id: str, sheet_name: str = "") -> ExcelSheetDTO | None:
        """Get a specific table by ID and optional sheet name

        Args:
            table_id (str): ID of the table to get
            sheet_name (str): Optional sheet name for Excel files

        Returns:
            Table | None: The requested Table or None if not found
        """
        table_item = self._excel_files.get(table_id)
        if table_item:
            return table_item.get_table_dto(sheet_name)
        return None

    def load_from_resource_id_url_param(self) -> None:
        """Load resource from URL parameter"""
        # Get the dynamic route parameter
        resource_id = self.resource_id if hasattr(self, "resource_id") else None

        if not resource_id:
            return None

        self.add_resource_model(resource_id)
