"""Base class for the brick's AI agents, running on pydantic-ai.

Replaces the hand-written OpenAI Responses loop of ``BaseFunctionAgentAi`` while keeping the
public surface subclasses and callers rely on: ``call_agent()`` is still a synchronous
generator of the same events, ``replay_events()`` still replays a serialised run without
calling a model, and the emitted event sequence is unchanged.

Conversation history is client-side (a pydantic-ai ``list[ModelMessage]`` carried on the
instance across turns). ``previous_response_id`` and ``openai_conversation_id`` are
deliberately not used: they are OpenAI-only, so relying on them would re-lock the agents to a
single provider in the place hardest to unwind.
"""

from abc import ABC, abstractmethod
from collections.abc import AsyncGenerator, Callable, Generator
from dataclasses import dataclass
from typing import Any, Generic, TypeVar, cast
from uuid import uuid4

from gws_core import BaseModelDTO
from pydantic_ai import Agent, ModelRetry, RunContext
from pydantic_ai.messages import ModelMessage
from pydantic_ai.models import Model
from pydantic_ai.settings import ModelSettings
from pydantic_ai.tools import Tool

from .agent_stream_adapter import AgentStreamAdapter
from .ai_model_factory import AiModelFactory
from .base_function_agent_events import (
    CreateSubAgent,
    FunctionCallEvent,
    FunctionErrorEvent,
    FunctionSuccessEvent,
    SubAgentSuccess,
    UserQueryEventBase,
)
from .sync_event_bridge import ProducerFactory, SyncEventBridge
from .table.agent_event_list import AgentEventList

T = TypeVar("T", bound=BaseModelDTO)
U = TypeVar("U", bound=UserQueryEventBase)


@dataclass
class AgentToolSpec:
    """Declarative description of a tool exposed to the model.

    The JSON schema is passed to pydantic-ai verbatim, so tool arguments keep the flat shape
    the serialised replay events record.

    Attributes:
        name: Tool name as the model sees it.
        description: Tells the model how and when to use the tool.
        parameters: JSON schema of the tool arguments, typically
            ``SomeConfig.model_json_schema()``.
    """

    name: str
    description: str
    parameters: dict


@dataclass
class AgentRunDeps(Generic[U]):
    """Dependencies handed to the tools of a run.

    Attributes:
        user_query: The user query event driving the run, carrying its tables and metadata.
        adapter: The stream adapter, used by tools to emit their own events.
    """

    user_query: U
    adapter: AgentStreamAdapter


class BasePydanticAgentAi(ABC, Generic[T, U]):
    """Base class for AI agents that call functions, implemented on pydantic-ai."""

    MAX_CONSECUTIVE_ERRORS = 5
    MAX_CONSECUTIVE_CALLS = 10

    # Only the API key is stored, never a provider client: these agents are held on Reflex
    # states, which must stay picklable.
    id: str
    _api_key: str | None
    _model: str | Model
    _temperature: float
    _event_list: AgentEventList[T]
    _skip_success_response: bool
    _message_history: list[ModelMessage]
    _replay_mode: bool = False
    _replayed_events: AgentEventList[T] | None = None

    def __init__(
        self,
        openai_api_key: str | None,
        model: str | Model,
        temperature: float,
        skip_success_response: bool = False,
    ):
        """Build an agent.

        Args:
            openai_api_key: API key for the configured provider, or None to let the provider
                read it from the environment.
            model: A ``provider:model`` string (``openai:gpt-4o``), or a pydantic-ai ``Model``
                instance, which is how tests inject ``TestModel`` / ``FunctionModel``.
            temperature: Sampling temperature for the model.
            skip_success_response: When True, the run stops after a successful tool call
                instead of asking the model for a closing message. Set on sub-agents, whose
                success is reported by the parent agent.
        """
        self.id = str(uuid4())
        self._api_key = openai_api_key
        self._model = model
        self._temperature = temperature
        self._event_list = AgentEventList[T]()
        self._skip_success_response = skip_success_response
        self._message_history = []

    # ------------------------------------------------------------------ public surface

    def call_agent(self, user_query: U) -> Generator[T, None, None]:
        """Run the agent for a user query, streaming its events.

        Args:
            user_query: The user's request.

        Yields:
            T: Stream of events during generation.
        """
        return SyncEventBridge[T].iterate(lambda emit: self._run(user_query, emit))

    async def call_agent_async(self, user_query: U) -> AsyncGenerator[T, None]:
        """Run the agent for a user query, streaming its events asynchronously.

        Args:
            user_query: The user's request.

        Yields:
            T: Stream of events during generation.
        """
        async for event in SyncEventBridge[T].aiterate(lambda emit: self._run(user_query, emit)):
            yield event

    def replay_events(
        self, events: list[T], user_query: U | None = None
    ) -> Generator[T, None, None]:
        """Replay a recorded run, re-executing its tools without calling a model.

        Args:
            events: The recorded events to replay.
            user_query: Optional user query to prepend to the replayed events.

        Yields:
            T: Each replayed event, plus the events produced by re-executing its tools.
        """
        self._replay_mode = True

        events_list: list[T]
        events_list = cast(list[T], [user_query]) + events if user_query is not None else events

        self._replayed_events = AgentEventList(events_list)

        return SyncEventBridge[T].iterate(lambda emit: self._replay(events_list, emit))

    def get_emitted_events(self) -> list[T]:
        """Get all events emitted during the last generation."""
        return self._event_list.get_all()

    def get_events(self) -> AgentEventList[T]:
        """Get the event list of the agent."""
        return self._event_list

    def get_last_user_query(self) -> U | None:
        """Get the last user query event."""
        return cast(U, self._event_list.last_event(cast(type[T], UserQueryEventBase)))

    def get_model(self) -> str:
        """Get the ``provider:model`` string of the model used by the agent."""
        return AiModelFactory.model_spec(self._model)

    def get_temperature(self) -> float:
        """Get the temperature used by the agent."""
        return self._temperature

    # ------------------------------------------------------------------ subclass hooks

    @abstractmethod
    def _get_ai_instruction(self, user_query: U) -> str:
        """Build the instructions for the model.

        Args:
            user_query: The user query event driving the run.

        Returns:
            The instructions handed to the model for this run.
        """

    @abstractmethod
    def _get_tools(self) -> list[AgentToolSpec]:
        """Declare the tools exposed to the model.

        Returns:
            The tool specifications.
        """

    @abstractmethod
    def _handle_function_call(
        self, function_call_event: FunctionCallEvent, user_query: U
    ) -> AsyncGenerator[T, None]:
        """Execute a tool call, emitting the events it produces.

        Called both when the model calls a tool and when a recorded run is replayed, so a
        replay re-executes exactly the same code path.

        Args:
            function_call_event: The tool call to execute.
            user_query: The user query event driving the run.

        Yields:
            T: Events produced while executing the tool.
        """

    # ------------------------------------------------------------------ run internals

    async def _run(self, user_query: U, emit: Callable[[T], None]) -> None:
        """Drive one agent run, emitting its events.

        Args:
            user_query: The user's request.
            emit: Callback pushing each event to the consumer.
        """
        adapter = AgentStreamAdapter[T](
            agent_id=self.id,
            emit=emit,
            event_list=self._event_list,
            stop_after_function_success=self._skip_success_response,
        )

        user_event = cast(T, user_query)
        adapter.emit(user_event)

        agent = self._build_agent(user_query, adapter)
        deps = AgentRunDeps(user_query=user_query, adapter=adapter)

        self._message_history = await adapter.stream_run(
            agent=agent,
            user_prompt=user_query.query,
            deps=deps,
            message_history=self._message_history or None,
            max_consecutive_calls=self.MAX_CONSECUTIVE_CALLS,
            max_consecutive_errors=self.MAX_CONSECUTIVE_ERRORS,
        )

    async def _replay(self, events: list[T], emit: Callable[[T], None]) -> None:
        """Replay recorded events, re-executing their tool calls.

        Args:
            events: The recorded events to replay.
            emit: Callback pushing each event to the consumer.
        """
        last_user_query: U | None = None

        for event in events:
            if isinstance(event, UserQueryEventBase):
                self._event_list.append(event)
                emit(event)
                last_user_query = cast(U, event)

            if isinstance(event, FunctionCallEvent):
                self._event_list.append(event)
                emit(event)
                if not last_user_query:
                    raise ValueError("No user query found before function call event")
                async for sub_event in self._handle_function_call(event, last_user_query):
                    self._event_list.append(sub_event)
                    emit(sub_event)

    def _build_agent(self, user_query: U, adapter: AgentStreamAdapter) -> Agent:
        """Build the pydantic-ai agent for a run.

        Instructions depend on the user query (they carry the table metadata), so the agent is
        built per run. Instructions are not part of the message history in pydantic-ai, which
        is exactly what lets them change between turns of the same conversation.

        Args:
            user_query: The user query event driving the run.
            adapter: The stream adapter the tools emit through.

        Returns:
            The configured pydantic-ai agent.
        """
        return Agent(
            model=AiModelFactory.build(self._model, self._api_key),
            instructions=self._get_ai_instruction(user_query),
            deps_type=AgentRunDeps,
            model_settings=ModelSettings(
                temperature=self._temperature,
                # Keep the iterative one-function-at-a-time processing the prompts rely on.
                parallel_tool_calls=False,
            ),
            retries={"tools": self.MAX_CONSECUTIVE_ERRORS},
            tools=[self._build_tool(spec) for spec in self._get_tools()],
        )

    def _build_tool(self, spec: AgentToolSpec) -> Tool:
        """Build a pydantic-ai tool dispatching to :meth:`_handle_function_call`.

        The declared JSON schema is used verbatim so tool arguments keep the flat shape the
        serialised replay events record.

        Args:
            spec: The tool specification.

        Returns:
            The pydantic-ai tool.
        """

        async def call_tool(ctx: RunContext[AgentRunDeps], **arguments: Any) -> str:
            return await self._dispatch_tool_call(
                spec.name, arguments, ctx.tool_call_id or "", ctx.deps
            )

        return Tool.from_schema(
            call_tool,
            name=spec.name,
            description=spec.description,
            json_schema=spec.parameters,
            takes_ctx=True,
        )

    async def _dispatch_tool_call(
        self, function_name: str, arguments: dict, call_id: str, deps: AgentRunDeps
    ) -> str:
        """Execute a tool call and report its outcome back to the model.

        Args:
            function_name: Name of the tool the model called.
            arguments: Arguments the model passed.
            call_id: The provider's tool call ID, carried onto the emitted events.
            deps: Dependencies of the run.

        Returns:
            The success message handed back to the model.

        Raises:
            ModelRetry: When the tool failed, so the model can correct itself. This is the
                pydantic-ai equivalent of the hand-written loop's error feedback turn.
        """
        adapter = deps.adapter
        function_call_event = FunctionCallEvent(
            call_id=call_id,
            response_id=adapter.current_response_id,
            function_name=function_name,
            arguments=arguments,
            agent_id=self.id,
        )

        success: FunctionSuccessEvent | None = None
        error: FunctionErrorEvent | None = None

        async for event in self._handle_function_call(
            function_call_event, cast(U, deps.user_query)
        ):
            adapter.emit(event)

            if isinstance(event, FunctionSuccessEvent) and event.agent_id == self.id:
                success = event
            if isinstance(event, FunctionErrorEvent) and event.agent_id == self.id:
                error = event

        if error:
            message = error.message
            if error.stack_trace:
                message = f"{error.message}\n\nStack trace:\n{error.stack_trace}"
            raise ModelRetry(f"{message}\n\nCan you fix the code?")

        if success:
            return success.function_response

        return "The function returned no result."

    # ------------------------------------------------------------------ sub-agents

    async def call_sub_agent(
        self,
        sub_agent: "BasePydanticAgentAi",
        user_query: UserQueryEventBase,
        parent_response_id: str,
        parent_call_id: str,
        parent_agent_id: str,
    ) -> AsyncGenerator[Any, None]:
        """Delegate to a sub-agent, yielding its events into the parent's stream.

        Args:
            sub_agent: The sub-agent to run.
            user_query: The request to pass to the sub-agent.
            parent_response_id: Response ID of the parent response that delegated.
            parent_call_id: Call ID of the parent tool call that delegated.
            parent_agent_id: ID of the delegating agent.

        Yields:
            Events emitted by the sub-agent, followed by a ``SubAgentSuccess`` reported at the
            parent's level when the sub-agent succeeded.
        """
        # Recorded so a replay can find which sub-agent handled which parent response.
        yield CreateSubAgent(response_id=parent_response_id, agent_id=sub_agent.id)

        producer: ProducerFactory

        if self._replay_mode:
            if not self._replayed_events:
                raise ValueError("No replayed events available in replay mode")
            create_sub_agent_event = self._replayed_events.find_create_sub_agent_event(
                parent_response_id
            )
            if not create_sub_agent_event:
                raise ValueError("Could not find sub agent ID in replayed events")
            sub_agent_events = self._replayed_events.get_agent_and_sub_agents_events(
                create_sub_agent_event.agent_id
            )
            # The user query is prepended: the replay needs it before the function calls.
            replayed = cast(list, [user_query]) + sub_agent_events
            sub_agent._replay_mode = True  # noqa: SLF001 - sibling of the same family
            sub_agent._replayed_events = AgentEventList(replayed)  # noqa: SLF001 - same as above

            def producer(emit):  # noqa: F811 - branch-specific producer
                return sub_agent._replay(replayed, emit)  # noqa: SLF001 - same as above
        else:
            if user_query is None:
                raise ValueError("user_query must be provided when not in replay mode")

            def producer(emit):  # noqa: F811 - branch-specific producer
                return sub_agent._run(user_query, emit)  # noqa: SLF001 - same as above

        success_event: FunctionSuccessEvent | None = None

        # Streamed rather than collected, so the sub-agent's text deltas and results reach the
        # UI as they happen instead of arriving in one burst when it finishes.
        async for event in SyncEventBridge.aiterate(producer):
            yield event

            if isinstance(event, FunctionSuccessEvent):
                success_event = event

        if success_event:
            yield SubAgentSuccess(
                call_id=parent_call_id,
                response_id=parent_response_id,
                function_response=(
                    f"{success_event.function_response} Continue with next steps if needed."
                ),
                agent_id=parent_agent_id,
            )
