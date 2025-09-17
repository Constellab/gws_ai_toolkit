from typing import Dict, List, cast

from gws_core import File, Table, TableImporter
from pandas import DataFrame


class TableItem:
    """Class to represent a dataframe with its name and file path"""

    name: str
    _tables: Dict[str, Table]  # Cache for sheet dataframes

    def __init__(self, name: str):
        self.name = name
        self._tables = {}  # Cache for sheet dataframes

    def get_sheet_names(self) -> List[str]:
        """Get list of sheet names for Excel files, or empty list for CSV"""
        return list(self._tables.keys())

    def has_multiple_sheets(self) -> bool:
        """Check if the file has multiple sheets"""
        return len(self.get_sheet_names()) > 1

    def get_default_table(self) -> Table:
        """Get the dataframe of the first sheet (or CSV data)"""
        sheet_names = self.get_sheet_names()
        if sheet_names:
            return self._tables[sheet_names[0]]
        return Table()

    def get_table(self, sheet_name: str = "") -> Table:
        """Get table for specific sheet (or CSV data if sheet_name is empty)"""
        # Use cached table if available
        if not sheet_name:
            return self.get_default_table()
        return self._tables[sheet_name]

    def get_dataframe(self, sheet_name: str = "") -> DataFrame:
        """Get dataframe for specific sheet (or CSV data if sheet_name is empty)"""
        table = self.get_table(sheet_name)
        return table.to_dataframe()

    def add_table(self, sheet_name: str, table: Table):
        """Add a Table object for a specific sheet"""
        self._tables[sheet_name] = table

    @staticmethod
    def from_file(name: str, file_path: str) -> "TableItem":
        """Create DataFrameItem from file path"""
        item = TableItem(name=name)

        file = File(file_path)

        extension = file.extension

        if not file.is_csv_or_excel():
            raise ValueError(f"Unsupported file extension: {extension}")

        tables: Dict[str, Table] = {}
        if extension == "csv":
            table = cast(Table, TableImporter.call(file, {}))
            table.name = name
            tables[name] = table
        else:  # Excel file
            tables = TableImporter.import_excel_multiple_sheets(file, {})

        for sheet_name, table in tables.items():
            table.name = f"{name}_{sheet_name}"
            item.add_table(sheet_name=sheet_name, table=table)

        return item

    @staticmethod
    def from_table(name: str, table: Table) -> "TableItem":
        """Create DataFrameItem from a Table object"""
        item = TableItem(name=name)
        table.name = name
        item.add_table(sheet_name=name, table=table)
        return item
