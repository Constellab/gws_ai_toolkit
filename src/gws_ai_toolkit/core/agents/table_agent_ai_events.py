from typing import Literal, Union

from gws_ai_toolkit.core.agents.base_function_agent_events import (
    ErrorEvent, FunctionErrorEvent, FunctionResultEventBase,
    ResponseCompletedEvent, ResponseCreatedEvent, TextDeltaEvent)
from gws_ai_toolkit.core.agents.plotly_agent_ai_events import \
    PlotGeneratedEvent
from gws_ai_toolkit.core.agents.table_transform_agent_ai_events import \
    TableTransformEvent


class SubAgentSuccess(FunctionResultEventBase):
    type: Literal["sub_agent_success"] = "sub_agent_success"


# Union type for all TableAgent events - includes specific events from sub-agents
TableAgentEvent = Union[
    TextDeltaEvent,
    PlotGeneratedEvent,
    TableTransformEvent,
    FunctionErrorEvent,
    ErrorEvent,
    ResponseCreatedEvent,
    ResponseCompletedEvent,
    SubAgentSuccess
]
