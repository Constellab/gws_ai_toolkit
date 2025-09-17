from typing import Literal, Union

import plotly.graph_objects as go

from gws_ai_toolkit.core.agents.base_function_agent_events import (
    ErrorEvent, FunctionResultEventBase, ResponseCompletedEvent,
    ResponseCreatedEvent, TextDeltaEvent)

# Typed event classes with literal types and direct attributes


class PlotGeneratedEvent(FunctionResultEventBase):
    type: Literal["plot_generated"] = "plot_generated"
    figure: go.Figure

    class Config:
        arbitrary_types_allowed = True  # Allow non-pydantic types like go.Figure


# Union type for all events
PlotlyAgentEvent = Union[
    TextDeltaEvent,
    PlotGeneratedEvent,
    ErrorEvent,
    ResponseCreatedEvent,
    ResponseCompletedEvent
]
