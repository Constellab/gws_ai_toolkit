from typing import Literal

from gws_core import BaseModelDTO, Table

from gws_ai_toolkit.core.agents.base_function_agent_events import UserQueryEventBase

# ============================================================================
# SERIALIZABLE VERSIONS (No Table objects)
# These are used for storage/transfer and contain only table keys
# ============================================================================


class SerializableUserQueryMultiTablesEvent(BaseModelDTO):
    """Serializable version of UserQueryMultiTablesEvent - uses table keys instead of Table objects"""

    type: Literal["user_tables"] = "user_tables"
    query: str
    agent_id: str
    table_keys: list[str]
    output_table_names: list[str] | None = None


class SerializableUserQueryTableEvent(BaseModelDTO):
    """Serializable version of UserQueryTableEvent - uses table key instead of Table object"""

    type: Literal["user_table"] = "user_table"
    query: str
    agent_id: str
    table_key: str


class SerializableUserQueryTableTransformEvent(BaseModelDTO):
    """Serializable version of UserQueryTableTransformEvent - uses table key instead of Table object"""

    type: Literal["user_table_transform"] = "user_table_transform"
    query: str
    agent_id: str
    table_key: str
    table_name: str | None = None
    output_table_name: str | None = None


# ============================================================================
# RUNTIME VERSIONS (With Table objects)
# These are used during agent execution and contain actual Table objects
# ============================================================================


class UserQueryMultiTablesEvent(UserQueryEventBase):
    type: Literal["user_tables"] = "user_tables"
    tables: dict[str, Table]
    output_table_names: list[str] | None = None

    class Config:
        arbitrary_types_allowed = True

    def get_tables_info(self) -> str:
        return "\n".join(
            self._get_table_ai_info(table_unique_name, table) for table_unique_name, table in self.tables.items()
        )

    def _get_table_ai_info(self, table_unique_name: str, table: Table) -> str:
        """Get AI info string for a specific table"""
        table_name = f"## '{table_unique_name}'"
        table_description = table.get_ai_description()
        return f"""{table_name}
{table_description}
"""

    def get_and_check_table(self, table_unique_name: str) -> Table:
        # Retrieve the specified table
        if not table_unique_name or not table_unique_name.strip():
            raise Exception("No table name provided in function arguments.")

        table_unique_name = table_unique_name.strip()
        if table_unique_name not in self.tables:
            raise Exception(f"Table '{table_unique_name}' not found. Available tables: {', '.join(self.tables.keys())}")
        return self.tables[table_unique_name]

    def to_serializable(self) -> SerializableUserQueryMultiTablesEvent:
        """Convert to serializable format (without Table objects)"""
        return SerializableUserQueryMultiTablesEvent(
            query=self.query,
            agent_id=self.agent_id,
            table_keys=list(self.tables.keys()),
            output_table_names=self.output_table_names,
        )

    @classmethod
    def from_serializable(
        cls, serializable: SerializableUserQueryMultiTablesEvent, tables: dict[str, Table]
    ) -> "UserQueryMultiTablesEvent":
        """Reconstruct from serializable format with actual Table objects"""
        filtered_tables = {key: tables[key] for key in serializable.table_keys if key in tables}

        return cls(
            query=serializable.query,
            agent_id=serializable.agent_id,
            tables=filtered_tables,
            output_table_names=serializable.output_table_names,
        )


class UserQueryTableEvent(UserQueryEventBase):
    type: Literal["user_table"] = "user_table"
    table: Table
    table_key: str | None = None  # Optional: key to identify the table for serialization

    class Config:
        arbitrary_types_allowed = True

    def to_serializable(self) -> SerializableUserQueryTableEvent:
        """Convert to serializable format (without Table object)

        Note: table_key must be set before calling this method
        """
        if self.table_key is None:
            raise ValueError("table_key must be set to serialize UserQueryTableEvent")

        return SerializableUserQueryTableEvent(
            query=self.query,
            agent_id=self.agent_id,
            table_key=self.table_key,
        )

    @classmethod
    def from_serializable(
        cls, serializable: SerializableUserQueryTableEvent, tables: dict[str, Table]
    ) -> "UserQueryTableEvent":
        """Reconstruct from serializable format with actual Table object"""
        if serializable.table_key not in tables:
            raise KeyError(f"Table '{serializable.table_key}' not found in provided tables")

        return cls(
            query=serializable.query,
            agent_id=serializable.agent_id,
            table=tables[serializable.table_key],
            table_key=serializable.table_key,
        )


class UserQueryTableTransformEvent(UserQueryEventBase):
    """User query event for table transformation with table name metadata"""

    type: Literal["user_table_transform"] = "user_table_transform"
    table: Table
    table_name: str | None = None
    output_table_name: str | None = None

    class Config:
        arbitrary_types_allowed = True

    def to_serializable(self) -> SerializableUserQueryTableTransformEvent:
        """Convert to serializable format (without Table object)

        Note: table_name must be set before calling this method
        """
        if self.table_name is None:
            raise ValueError("table_name must be set to serialize UserQueryTableTransformEvent")

        return SerializableUserQueryTableTransformEvent(
            query=self.query,
            agent_id=self.agent_id,
            table_key=self.table_name,
            table_name=self.table_name,
            output_table_name=self.output_table_name,
        )

    @classmethod
    def from_serializable(
        cls, serializable: SerializableUserQueryTableTransformEvent, tables: dict[str, Table]
    ) -> "UserQueryTableTransformEvent":
        """Reconstruct from serializable format with actual Table object"""
        if serializable.table_key not in tables:
            raise KeyError(f"Table '{serializable.table_key}' not found in provided tables")

        return cls(
            query=serializable.query,
            agent_id=serializable.agent_id,
            table=tables[serializable.table_key],
            table_name=serializable.table_name,
            output_table_name=serializable.output_table_name,
        )
