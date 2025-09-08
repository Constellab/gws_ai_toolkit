import os
from typing import List, Optional

import pandas as pd
import reflex as rx
from gws_core import File, ResourceModel

from .dataframe_item import DataFrameItem


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

    def _get_current_dataframe_item(self) -> Optional[DataFrameItem]:
        """Create DataFrameItem from current file info"""
        if not self.current_file_path or not os.path.exists(self.current_file_path):
            return None
        return DataFrameItem(self.current_file_name, self.current_file_path)

    def set_resource(self, resource: ResourceModel):
        """Set the resource to analyze and load it as dataframe

        Args:
            resource (ResourceModel): Resource model to set
        """
        try:
            file = resource.get_resource()
            if not isinstance(file, File) or not file.is_csv_or_excel():
                print("Resource is not a valid CSV or Excel file")
                return

            self.current_file_path = file.path
            self.current_file_name = os.path.splitext(os.path.basename(file.path))[0]

            # Test if file can be loaded
            df_item = self._get_current_dataframe_item()
            if df_item:
                test_df = df_item.get_default_dataframe()
                if test_df.empty:
                    print(f"The dataframe is empty: {file.path}")
                    return

                # Set default sheet for Excel files
                if df_item.get_sheet_names():
                    self.current_sheet_name = df_item.get_sheet_names()[0]
                else:
                    self.current_sheet_name = ""

        except Exception as e:
            print(f"Error loading resource as dataframe: {e}")

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
        """Get the current active dataframe"""
        df_item = self._get_current_dataframe_item()
        if df_item:
            if self.current_sheet_name:
                return df_item.get_dataframe(self.current_sheet_name)
            else:
                return df_item.get_default_dataframe()
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

    def validate_resource(self, resource: ResourceModel) -> bool:
        """Validate if resource is an Excel or CSV file

        Args:
            resource (ResourceModel): Resource to validate

        Returns:
            bool: True if resource is Excel/CSV, False otherwise
        """
        try:
            file = resource.get_resource()
            if not isinstance(file, File):
                return False
            return file.is_csv_or_excel()
        except Exception:
            return False

    def _load_resource_from_id(self) -> Optional[ResourceModel]:
        """Load resource from URL parameter"""
        # Get the dynamic route parameter
        resource_id = self.resource_id if hasattr(self, 'resource_id') else None

        if not resource_id:
            return None

        resource_model = ResourceModel.get_by_id(resource_id)
        if not resource_model:
            raise ValueError(f"Resource with id {resource_id} not found")

        return resource_model

    def open_current_resource_file(self):
        """Open the current resource file (for compatibility with existing UI)"""
        if self.current_file_path:
            # This would typically open the file in an external application
            # Implementation depends on the platform and requirements
            pass
