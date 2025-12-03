from typing import Literal

from gws_core import PlotlyResource

from gws_ai_toolkit.core.agents.base_function_agent_events import (
    BaseFunctionAgentEvent,
    FunctionSuccessEvent,
)
from gws_ai_toolkit.core.agents.table.table_agent_event_base import UserQueryTableEvent

# Typed event classes with literal types and direct attributes


class PlotGeneratedEvent(FunctionSuccessEvent):
    type: Literal["plot_generated"] = "plot_generated"
    plot: PlotlyResource
    code: str  # The Python code that generated the figure

    class Config:
        arbitrary_types_allowed = True  # Allow non-pydantic types like go.Figure


# Union type for all events
PlotlyAgentEvent = PlotGeneratedEvent | UserQueryTableEvent | BaseFunctionAgentEvent
