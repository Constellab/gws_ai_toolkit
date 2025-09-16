from datetime import datetime
from typing import Any, Literal, Optional, Union

import plotly.graph_objects as go
from gws_core import BaseModelDTO


# Typed event classes with literal types and direct attributes
class TextDeltaEvent(BaseModelDTO):
    type: Literal["text_delta"] = "text_delta"
    delta: str


class FunctionCallStartedEvent(BaseModelDTO):
    type: Literal["function_call_started"] = "function_call_started"
    call_data: Any


class PlotGeneratedEvent(BaseModelDTO):
    type: Literal["plot_generated"] = "plot_generated"
    figure: go.Figure
    code: str
    call_id: Optional[str]
    response_id: Optional[str]

    class Config:
        arbitrary_types_allowed = True  # Allow non-pydantic types like go.Figure


class ErrorEvent(BaseModelDTO):
    type: Literal["error"] = "error"
    message: str
    code: Optional[str]
    error_type: str
    consecutive_error_count: int
    is_recoverable: bool


class ResponseCreatedEvent(BaseModelDTO):
    type: Literal["response_created"] = "response_created"
    response_id: Optional[str]


class ResponseCompletedEvent(BaseModelDTO):
    type: Literal["response_completed"] = "response_completed"


class OutputItemAddedEvent(BaseModelDTO):
    type: Literal["output_item_added"] = "output_item_added"
    item_data: Any


class OutputItemDoneEvent(BaseModelDTO):
    type: Literal["output_item_done"] = "output_item_done"
    item_data: Any


# Union type for all events
PlotAgentEvent = Union[
    TextDeltaEvent,
    FunctionCallStartedEvent,
    PlotGeneratedEvent,
    ErrorEvent,
    ResponseCreatedEvent,
    ResponseCompletedEvent,
    OutputItemAddedEvent,
    OutputItemDoneEvent
]
