"""Events of the knowledge-base agent, in this brick's agent event vocabulary.

The agent emits the base function-agent events (created / text delta / function call / completed /
error) plus the one event of its own tool, so the chat conversation consuming the stream dispatches
on the same types it already knows.
"""

from typing import Literal

from gws_ai_toolkit.core.agents.agent_events import (
    BaseFunctionAgentEvent,
    FunctionSuccessEvent,
    UserQueryTextEvent,
)


class KnowledgeSearchSuccessEvent(FunctionSuccessEvent):
    """What ``search_knowledge`` reported back to the model.

    ``FunctionSuccessEvent`` carries no ``type`` of its own by design, so each tool family declares
    one. Emitting it is what gets the tool result *persisted in stream order* — between the call and
    the answer it led to — which is the order a restore replays.
    """

    type: Literal["knowledge_search_success"] = "knowledge_search_success"


# Union of everything a knowledge-base agent run emits.
KnowledgeBaseAgentEvent = (
    BaseFunctionAgentEvent | KnowledgeSearchSuccessEvent | UserQueryTextEvent
)
