from typing import Dict, List, Literal, Optional, Union

from gws_core import Table

from gws_ai_toolkit.core.agents.base_function_agent_events import (
    ErrorEvent, FunctionErrorEvent, FunctionSuccessEvent,
    ResponseCompletedEvent, ResponseCreatedEvent, TextDeltaEvent)


class MultiTableTransformEvent(FunctionSuccessEvent):
    type: Literal["multi_table_transform"] = "multi_table_transform"
    tables: Dict[str, Table]  # Dictionary of table_name -> Table
    table_names: Optional[List[str]] = None
    code: str  # The Python code that generated the tables

    class Config:
        arbitrary_types_allowed = True  # Allow non-pydantic types like pd.DataFrame


# Union type for all events
MultiTableTransformAgentEvent = Union[
    TextDeltaEvent,
    MultiTableTransformEvent,
    FunctionErrorEvent,
    ErrorEvent,
    ResponseCreatedEvent,
    ResponseCompletedEvent
]
