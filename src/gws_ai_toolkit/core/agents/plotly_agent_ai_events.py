from typing import Literal, Optional, Union

import plotly.graph_objects as go
from gws_core import BaseModelDTO


# Typed event classes with literal types and direct attributes
class TextDeltaEvent(BaseModelDTO):
    type: Literal["text_delta"] = "text_delta"
    delta: str


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
    call_id: str | None = None


class ResponseCreatedEvent(BaseModelDTO):
    type: Literal["response_created"] = "response_created"
    response_id: Optional[str]


class ResponseCompletedEvent(BaseModelDTO):
    type: Literal["response_completed"] = "response_completed"


# Union type for all events
PlotAgentEvent = Union[
    TextDeltaEvent,
    PlotGeneratedEvent,
    ErrorEvent,
    ResponseCreatedEvent,
    ResponseCompletedEvent
]
