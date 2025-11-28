from typing import Literal

from gws_ai_toolkit.core.agents.base_function_agent_events import (
    BaseFunctionAgentEvent,
    FunctionSuccessEvent,
)
from gws_ai_toolkit.core.agents.multi_table_agent_ai_events import MultiTableTransformEvent
from gws_ai_toolkit.core.agents.plotly_agent_ai_events import PlotGeneratedEvent
from gws_ai_toolkit.core.agents.table_transform_agent_ai_events import TableTransformEvent


class SubAgentSuccess(FunctionSuccessEvent):
    type: Literal["sub_agent_success"] = "sub_agent_success"


# Union type for all TableAgent events - includes specific events from sub-agents
TableAgentEvent = (
    BaseFunctionAgentEvent | PlotGeneratedEvent | TableTransformEvent | MultiTableTransformEvent | SubAgentSuccess
)
