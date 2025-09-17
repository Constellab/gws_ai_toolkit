from typing import Literal, Optional, Union

from gws_core import Table

from gws_ai_toolkit.core.agents.base_function_agent_events import (
    ErrorEvent, FunctionResultEventBase, ResponseCompletedEvent,
    ResponseCreatedEvent, TextDeltaEvent)

# Typed event classes with literal types and direct attributes


class TableTransformEvent(FunctionResultEventBase):
    type: Literal["dataframe_transform"] = "dataframe_transform"
    table: Table
    table_name: Optional[str] = None

    class Config:
        arbitrary_types_allowed = True  # Allow non-pydantic types like pd.DataFrame


# Union type for all events
DataFrameTransformAgentEvent = Union[
    TextDeltaEvent,
    TableTransformEvent,
    ErrorEvent,
    ResponseCreatedEvent,
    ResponseCompletedEvent
]
