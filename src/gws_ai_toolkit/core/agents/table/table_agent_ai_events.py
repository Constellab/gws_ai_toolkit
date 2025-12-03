from typing import Literal

from gws_ai_toolkit.core.agents.base_function_agent_events import (
    BaseFunctionWithSubAgentEvent,
    BaseFunctionWithSubAgentSerializableEvent,
    FunctionSuccessEvent,
)
from gws_ai_toolkit.core.agents.table.multi_table_agent_ai_events import MultiTableTransformEvent
from gws_ai_toolkit.core.agents.table.plotly_agent_ai_events import PlotGeneratedEvent
from gws_ai_toolkit.core.agents.table.table_agent_event_base import (
    SerializableUserQueryMultiTablesEvent,
    UserQueryMultiTablesEvent,
)
from gws_ai_toolkit.core.agents.table.table_transform_agent_ai_events import TableTransformEvent


class InstanciatateSubAgent(FunctionSuccessEvent):
    type: Literal["instantiate_sub_agent"] = "instantiate_sub_agent"
    sub_agent_name: str
    sub_agent_type: str


# Union type for all TableAgent events - includes specific events from sub-agents
TableAgentEvent = (
    BaseFunctionWithSubAgentEvent
    | PlotGeneratedEvent
    | TableTransformEvent
    | MultiTableTransformEvent
    | UserQueryMultiTablesEvent
)

SerializableTableAgentEvent = SerializableUserQueryMultiTablesEvent | BaseFunctionWithSubAgentSerializableEvent
