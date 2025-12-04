from typing import Literal

from gws_core import Table

from gws_ai_toolkit.core.agents.base_function_agent_events import (
    BaseFunctionAgentEvent,
    FunctionSuccessEvent,
)
from gws_ai_toolkit.core.agents.table.table_agent_event_base import UserQueryMultiTablesEvent


class MultiTableTransformEvent(FunctionSuccessEvent):
    type: Literal["multi_table_transform"] = "multi_table_transform"
    tables: dict[str, Table]  # Dictionary of table_name -> Table
    code: str  # The Python code that generated the tables

    class Config:
        arbitrary_types_allowed = True  # Allow non-pydantic types like pd.DataFrame


# Union type for all events
MultiTableTransformAgentEvent = (
    MultiTableTransformEvent | UserQueryMultiTablesEvent | BaseFunctionAgentEvent
)
