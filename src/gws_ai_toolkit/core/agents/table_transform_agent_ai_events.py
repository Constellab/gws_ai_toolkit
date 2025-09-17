from typing import Literal, Optional, Union

from gws_core import Table

from gws_ai_toolkit.core.agents.base_function_agent_events import (
    ErrorEvent, FunctionErrorEvent, FunctionResultEventBase,
    ResponseCompletedEvent, ResponseCreatedEvent, TextDeltaEvent)

# Typed event classes with literal types and direct attributes


class TableTransformEvent(FunctionResultEventBase):
    type: Literal["dataframe_transform"] = "dataframe_transform"
    table: Table
    table_name: Optional[str] = None
    code: str  # The Python code that generated the table

    class Config:
        arbitrary_types_allowed = True  # Allow non-pydantic types like pd.DataFrame


# Union type for all events
DataFrameTransformAgentEvent = Union[
    TextDeltaEvent,
    TableTransformEvent,
    FunctionErrorEvent,
    ErrorEvent,
    ResponseCreatedEvent,
    ResponseCompletedEvent
]
