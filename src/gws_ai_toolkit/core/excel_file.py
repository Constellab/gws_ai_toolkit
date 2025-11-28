from dataclasses import dataclass
from typing import cast

from gws_core import File, Table, TableImporter
from pandas import DataFrame


@dataclass
class ExcelFileDTO:
    id: str
    name: str
    sheets: list[str] | None  # null if there is no multiple sheets


@dataclass
class ExcelSheetDTO:
    id: str
    name: str
    sheet_name: str | None  # null if there is no multiple sheets
    table: Table

    def get_unique_name(self) -> str:
        """Get unique name for the sheet (name > sheet_name)"""
        if self.sheet_name:
            return f"{self.name}_{self.sheet_name}"
        return self.name


class ExcelFile:
    """Class to represent a dataframe with its name and file path"""

    id: str
    name: str
    _tables: dict[str, Table]  # Cache for sheet dataframes

    # provided if the sheet/file is associated with a resource model
    resource_model_id: str | None = None

    def __init__(self, id_: str, name: str, resource_model_id: str | None = None):
        self.id = id_
        self.name = name
        self._tables = {}  # Cache for sheet dataframes
        self.resource_model_id = resource_model_id

    def get_sheet_names(self) -> list[str]:
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

    def get_table_dto(self, sheet_name: str = "") -> ExcelSheetDTO:
        """Convert specific table to TableDTO"""
        table = self.get_table(sheet_name)
        return ExcelSheetDTO(
            id=self.id,
            name=self.name,
            sheet_name=sheet_name,
            table=table,
        )

    def get_dataframe(self, sheet_name: str = "") -> DataFrame:
        """Get dataframe for specific sheet (or CSV data if sheet_name is empty)"""
        table = self.get_table(sheet_name)
        return table.to_dataframe()

    def add_table(self, sheet_name: str, table: Table):
        """Add a Table object for a specific sheet"""
        self._tables[sheet_name] = table

    @staticmethod
    def from_file(id_: str, name: str, file_path: str, resource_model_id: str | None = None) -> "ExcelFile":
        """Create DataFrameItem from file path"""
        item = ExcelFile(id_=id_, name=name, resource_model_id=resource_model_id)

        file = File(file_path)

        extension = file.extension

        if not file.is_csv_or_excel():
            raise ValueError(f"Unsupported file extension: {extension} !")

        tables: dict[str, Table] = {}
        if extension == "csv":
            # set format_header_names to True to ensure consistent naming because aggrid
            # component has some problem with column names with special caracter (like dot or ")
            table = cast(Table, TableImporter.call(file, {"format_header_names": True}))
            table.name = name
            tables[name] = table
        else:  # Excel file
            tables = TableImporter.import_excel_multiple_sheets(file, {"format_header_names": True})

        for sheet_name, table in tables.items():
            if sheet_name == name:
                # Avoid duplicate names
                table.name = f"{name}"
            else:
                table.name = f"{name}_{sheet_name}"
            item.add_table(sheet_name=sheet_name, table=table)

        return item

    def to_dto(self) -> ExcelFileDTO:
        """Convert TableItem to TableItemDTO"""
        return ExcelFileDTO(
            id=self.id,
            name=self.name,
            sheets=self.get_sheet_names() if self.has_multiple_sheets() else None,
        )

    @staticmethod
    def from_table(id_: str, name: str, table: Table, resource_model_id: str | None = None) -> "ExcelFile":
        """Create DataFrameItem from a Table object"""
        item = ExcelFile(id_=id_, name=name, resource_model_id=resource_model_id)
        table.name = name
        item.add_table(sheet_name=name, table=table)
        return item
