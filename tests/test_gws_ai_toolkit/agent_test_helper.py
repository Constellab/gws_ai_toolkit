"""Helpers to drive the table agents from a script instead of a real model.

The table agent family shares one pydantic-ai model instance: ``TableAgentAi`` hands its own
``model`` down to the ``PlotlyAgentAi`` / ``TableTransformAgentAi`` / ``MultiTableAgentAi``
sub-agents it creates. A single scripted model therefore has to answer every agent in the
family, which it does by recognising each agent from the tools it was given and replaying that
agent's own list of turns.

No network call is made: everything runs through ``pydantic_ai.models.function.FunctionModel``.
"""

import json
from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from typing import Any

from pydantic_ai.messages import ModelMessage, ModelResponse
from pydantic_ai.models.function import AgentInfo, DeltaToolCall, FunctionModel

# Agent kinds, identified by the tools the agent exposes.
ORCHESTRATOR = "orchestrator"
PLOTLY = "plotly"
TRANSFORM = "transform"
MULTI_TABLE = "multi_table"


@dataclass
class ToolCall:
    """A scripted tool call for one model turn.

    Attributes:
        name: Name of the tool to call.
        args: Arguments to pass to the tool.
    """

    name: str
    args: dict


@dataclass
class ScriptedModel:
    """Scripts the answers of every agent in the table agent family.

    Attributes:
        script: Turns to replay per agent kind. Each entry is either a ``ToolCall`` or a
            string, which is streamed back as plain text in two chunks so that text delta
            handling is exercised.
        calls: Records ``(agent_kind, turn_index)`` for every model request, so a test can
            assert how many turns each agent took.
    """

    script: dict[str, list[ToolCall | str]]
    calls: list[tuple[str, int]] = field(default_factory=list)

    def build(self) -> FunctionModel:
        """Build the pydantic-ai model replaying this script.

        Returns:
            A ``FunctionModel`` usable as the ``model`` argument of any agent in the family.
        """
        return FunctionModel(stream_function=self._stream)

    async def _stream(self, messages: list[ModelMessage], info: AgentInfo) -> AsyncIterator[Any]:
        """Stream the next scripted turn for whichever agent is calling.

        Args:
            messages: The calling agent's message history.
            info: Agent info, whose tool names identify the calling agent.

        Yields:
            Text chunks or tool call deltas, as pydantic-ai's ``FunctionModel`` expects.

        Raises:
            AssertionError: If the script has no turn left for that agent.
        """
        kind = self.agent_kind(info)
        turn = sum(1 for message in messages if isinstance(message, ModelResponse))
        self.calls.append((kind, turn))

        turns = self.script.get(kind, [])
        assert turn < len(turns), (
            f"No scripted turn {turn} for agent '{kind}' (script has {len(turns)}). "
            f"Tools: {sorted(t.name for t in info.function_tools)}"
        )

        answer = turns[turn]

        if isinstance(answer, ToolCall):
            tool_call_id = f"call_{kind}_{turn}"
            yield {0: DeltaToolCall(name=answer.name, tool_call_id=tool_call_id)}
            # Arguments arrive in two chunks so partial tool-call deltas are exercised.
            payload = json.dumps(answer.args)
            split = len(payload) // 2
            yield {0: DeltaToolCall(json_args=payload[:split], tool_call_id=tool_call_id)}
            yield {0: DeltaToolCall(json_args=payload[split:], tool_call_id=tool_call_id)}
            return

        # Plain text answer, streamed in two deltas.
        split = max(1, len(answer) // 2)
        yield answer[:split]
        yield answer[split:]

    @staticmethod
    def agent_kind(info: AgentInfo) -> str:
        """Identify which agent of the family is calling, from its tool names.

        Args:
            info: Agent info carrying the available tools.

        Returns:
            One of the agent kind constants.

        Raises:
            AssertionError: If the tool set matches no known agent.
        """
        tool_names = {tool.name for tool in info.function_tools}

        if "generate_plot" in tool_names:
            return ORCHESTRATOR
        if "generate_plotly_figure" in tool_names:
            return PLOTLY
        if "transform_dataframe" in tool_names:
            return TRANSFORM
        if "transform_multiple_tables" in tool_names:
            return MULTI_TABLE

        raise AssertionError(f"Unrecognised agent, tools: {sorted(tool_names)}")
