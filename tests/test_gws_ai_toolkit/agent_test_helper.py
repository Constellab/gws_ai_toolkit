"""Helpers to drive this brick's agents from a script instead of a real model.

Two scripted models, sharing how a turn is streamed:

- :class:`ScriptedModel`, for the table agent family. Those agents share one pydantic-ai model
  instance — ``TableAgentAi`` hands its own ``model`` down to the ``PlotlyAgentAi`` /
  ``TableTransformAgentAi`` / ``MultiTableAgentAi`` sub-agents it creates — so a single scripted
  model has to answer every agent in the family, which it does by recognising each agent from the
  tools it was given and replaying that agent's own list of turns.
- :class:`SingleAgentScriptedModel`, for an agent with no sub-agents, which also records the tools
  and the history of every request it answered.

No network call is made: everything runs through ``pydantic_ai.models.function.FunctionModel``.
"""

import json
from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from typing import Any

from pydantic_ai.messages import ModelMessage, ModelResponse
from pydantic_ai.models.function import AgentInfo, DeltaToolCall, FunctionModel
from pydantic_ai.settings import ModelSettings

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
class ScriptedTurn:
    """One scripted model turn: text first, then a tool call, either of them optional.

    A turn with both is what a model does when it says something before searching, which is the
    case a turn scripted as a bare string or a bare :class:`ToolCall` cannot express.

    Attributes:
        text: Text streamed back, in two deltas. None for a turn that only calls a tool.
        tool_call: The tool call ending the turn. None for a turn that only answers.
    """

    text: str | None = None
    tool_call: ToolCall | None = None


# What a turn may be written as in a script: a bare string for plain text, a bare tool call, or
# both at once.
ScriptedAnswer = ScriptedTurn | ToolCall | str


def as_scripted_turn(answer: ScriptedAnswer) -> ScriptedTurn:
    """Normalise a scripted answer into a turn.

    Args:
        answer: The scripted answer, in any of its accepted shapes.

    Returns:
        The equivalent turn.
    """
    if isinstance(answer, ScriptedTurn):
        return answer
    if isinstance(answer, ToolCall):
        return ScriptedTurn(tool_call=answer)
    return ScriptedTurn(text=answer)


def stream_items_of_turn(turn: ScriptedTurn, tool_call_id: str) -> list[Any]:
    """The ``FunctionModel`` stream items replaying one turn.

    Text is split in two deltas and tool arguments in two chunks, so partial text deltas and
    partial tool-call deltas are both exercised.

    Args:
        turn: The turn to replay.
        tool_call_id: Call id to stamp on the tool call, unique within the run.

    Returns:
        The items to yield from a ``stream_function``, in order.
    """
    items: list[Any] = []

    if turn.text:
        split = max(1, len(turn.text) // 2)
        items.append(turn.text[:split])
        items.append(turn.text[split:])

    if turn.tool_call:
        items.append({0: DeltaToolCall(name=turn.tool_call.name, tool_call_id=tool_call_id)})
        payload = json.dumps(turn.tool_call.args)
        split = len(payload) // 2
        items.append({0: DeltaToolCall(json_args=payload[:split], tool_call_id=tool_call_id)})
        items.append({0: DeltaToolCall(json_args=payload[split:], tool_call_id=tool_call_id)})

    return items


@dataclass
class SingleAgentScriptedModel:
    """Scripts the turns of one agent, recording what it was asked on each request.

    The counterpart of :class:`ScriptedModel` for an agent that has no sub-agents: there is one
    list of turns rather than one per agent kind, and the requests are recorded so a test can
    assert which tools were offered and what history the model was shown.

    Attributes:
        turns: One entry per model request; see :data:`ScriptedAnswer`.
        tool_names_seen: The tools the agent exposed on each request.
        messages_seen: The history handed to the model on each request.
        instructions_seen: The instructions handed to the model on each request.
        model_settings_seen: The model settings of each request, temperature included.
    """

    turns: list[ScriptedAnswer]
    tool_names_seen: list[list[str]] = field(default_factory=list)
    messages_seen: list[list[ModelMessage]] = field(default_factory=list)
    instructions_seen: list[str | None] = field(default_factory=list)
    model_settings_seen: list[ModelSettings | None] = field(default_factory=list)

    def build(self) -> FunctionModel:
        """The pydantic-ai model replaying this script."""
        return FunctionModel(stream_function=self._stream)

    async def _stream(self, messages: list[ModelMessage], info: AgentInfo) -> AsyncIterator[Any]:
        """Stream the next scripted turn.

        Args:
            messages: The agent's message history.
            info: Agent info, carrying the tools the agent exposed.

        Yields:
            Text chunks or tool call deltas, as pydantic-ai's ``FunctionModel`` expects.

        Raises:
            AssertionError: If the script has no turn left.
        """
        self.tool_names_seen.append(sorted(tool.name for tool in info.function_tools))
        self.messages_seen.append(list(messages))
        self.instructions_seen.append(info.instructions)
        self.model_settings_seen.append(info.model_settings)

        index = sum(1 for message in messages if isinstance(message, ModelResponse))
        assert index < len(self.turns), f"No scripted turn {index} (script has {len(self.turns)})"

        for item in stream_items_of_turn(as_scripted_turn(self.turns[index]), f"call_{index}"):
            yield item


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

        for item in stream_items_of_turn(
            as_scripted_turn(turns[turn]), f"call_{kind}_{turn}"
        ):
            yield item

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
