from typing import Literal, Union

import pandas as pd

from gws_ai_toolkit.core.agents.base_function_agent_events import (
    ErrorEvent, FunctionResultEventBase, ResponseCompletedEvent,
    ResponseCreatedEvent, TextDeltaEvent)

# Typed event classes with literal types and direct attributes


class DataFrameTransformEvent(FunctionResultEventBase):
    type: Literal["dataframe_transform"] = "dataframe_transform"
    dataframe: pd.DataFrame

    class Config:
        arbitrary_types_allowed = True  # Allow non-pydantic types like pd.DataFrame


# Union type for all events
DataFrameTransformAgentEvent = Union[
    TextDeltaEvent,
    DataFrameTransformEvent,
    ErrorEvent,
    ResponseCreatedEvent,
    ResponseCompletedEvent
]