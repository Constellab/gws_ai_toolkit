from typing import Literal

from gws_core import Table

from gws_ai_toolkit.core.agents.base_function_agent_events import (
    BaseFunctionAgentEvent,
    FunctionSuccessEvent,
)

# Typed event classes with literal types and direct attributes


class TableTransformEvent(FunctionSuccessEvent):
    type: Literal["dataframe_transform"] = "dataframe_transform"
    table: Table
    table_name: str | None = None
    code: str  # The Python code that generated the table

    class Config:
        arbitrary_types_allowed = True  # Allow non-pydantic types like pd.DataFrame


# Union type for all events
DataFrameTransformAgentEvent = BaseFunctionAgentEvent | TableTransformEvent
