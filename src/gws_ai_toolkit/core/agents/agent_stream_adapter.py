"""Adapter translating a pydantic-ai agent run into this brick's agent event vocabulary.

This is the single place where pydantic-ai's streaming shape is mapped onto the
``ResponseCreatedEvent`` / ``TextDeltaEvent`` / ``FunctionCallEvent`` / ``ResponseCompletedEvent``
sequence the rest of the brick consumes. Every agent ported to pydantic-ai drives its run
through this adapter rather than re-deriving the mapping, so the chat conversations, the
replay serialisation and the Reflex components keep working unchanged.

Mapping
-------

===============================================  ==========================================
pydantic-ai                                      brick event
===============================================  ==========================================
``ModelRequestNode`` entered                     ``ResponseCreatedEvent``
``PartStartEvent`` / ``PartDeltaEvent`` (text)   ``TextDeltaEvent``
``FunctionToolCallEvent``                        ``FunctionCallEvent``
tool body                                        whatever the tool emits (code, results, ...)
``ModelRequestNode`` text accumulated            ``ResponseFullTextEvent``
``CallToolsNode`` finished                       ``ResponseCompletedEvent``
===============================================  ==========================================

``ResponseFullTextEvent`` and ``ResponseCompletedEvent`` are deliberately held back until the
tool calls of that response have run. pydantic-ai executes tools in the node *after* the model
request, whereas the OpenAI Responses stream reported them inside it. Deferring the two closing
events restores the original ordering, which matters because
:meth:`AgentEventList.get_agent_and_sub_agents_events` groups sub-agent events by the window
between a response's created and completed events.
"""

from collections.abc import Callable
from typing import Any, Generic, TypeVar, cast
from uuid import uuid4

from gws_core import BaseModelDTO
from pydantic_ai import Agent, UnexpectedModelBehavior, UsageLimitExceeded
from pydantic_ai.messages import (
    FunctionToolCallEvent,
    ModelMessage,
    PartDeltaEvent,
    PartStartEvent,
    TextPart,
    TextPartDelta,
)
from pydantic_ai.usage import UsageLimits

from .base_function_agent_events import (
    ErrorEvent,
    FunctionCallEvent,
    FunctionSuccessEvent,
    ResponseCompletedEvent,
    ResponseCreatedEvent,
    ResponseFullTextEvent,
    TextDeltaEvent,
)
from .table.agent_event_list import AgentEventList

T = TypeVar("T", bound=BaseModelDTO)

EmitCallback = Callable[[Any], None]


class AgentStreamAdapter(Generic[T]):
    """Streams a pydantic-ai agent run out as brick agent events.

    Attributes:
        current_response_id: Response ID of the model request being streamed. Tools read it
            so the events they emit are attributed to the response that called them.
    """

    _agent_id: str
    _emit: EmitCallback
    _event_list: AgentEventList[T]
    _stop_after_function_success: bool

    _current_response_id: str
    _function_success_seen: bool
    # Response whose closing events are still pending; see the module docstring.
    _pending_response: tuple[str, str] | None

    def __init__(
        self,
        agent_id: str,
        emit: EmitCallback,
        event_list: AgentEventList[T],
        stop_after_function_success: bool = False,
    ) -> None:
        """Build an adapter for a single agent run.

        Args:
            agent_id: ID of the agent being run, stamped onto every emitted event.
            emit: Callback pushing an event to the consumer.
            event_list: The agent's event list, appended to as events are emitted.
            stop_after_function_success: When True, the run stops as soon as one of this
                agent's tools reports success instead of going back to the model for a
                closing message. Used for sub-agents, whose success is reported by the
                parent agent.
        """
        self._agent_id = agent_id
        self._emit = emit
        self._event_list = event_list
        self._stop_after_function_success = stop_after_function_success
        self._current_response_id = ""
        self._function_success_seen = False
        self._pending_response = None

    @property
    def current_response_id(self) -> str:
        """Response ID of the model request currently being streamed."""
        return self._current_response_id

    def emit(self, event: T) -> None:
        """Emit an event to the consumer and record it on the agent's event list.

        Tools call this to surface their own domain events (generated code, produced tables,
        errors) in the middle of the stream.

        Args:
            event: The event to emit.
        """
        self._event_list.append(event)

        if isinstance(event, FunctionSuccessEvent) and event.agent_id == self._agent_id:
            self._function_success_seen = True

        self._emit(event)

    async def stream_run(
        self,
        agent: Agent,
        user_prompt: str,
        deps: Any,
        message_history: list[ModelMessage] | None,
        max_consecutive_calls: int,
        max_consecutive_errors: int,
    ) -> list[ModelMessage]:
        """Run a pydantic-ai agent, emitting brick events as the run progresses.

        Args:
            agent: The pydantic-ai agent to run.
            user_prompt: The user's request for this turn.
            deps: Dependencies handed to the agent's tools.
            message_history: Conversation history from previous turns, or None for a fresh
                conversation. History is client-side: no provider-side conversation handle
                is used, so the agents stay portable across providers.
            max_consecutive_calls: Cap on model requests for this run.
            max_consecutive_errors: Cap on tool retries, reported in the error message when
                the budget is exhausted.

        Returns:
            The full message history after the run, to be carried into the next turn. On a
            run that ended in an error the history from before the run is returned unchanged,
            so a failed turn does not poison the conversation.
        """
        history_before = list(message_history or [])

        try:
            async with agent.iter(
                user_prompt,
                deps=deps,
                message_history=message_history,
                usage_limits=UsageLimits(request_limit=max_consecutive_calls),
            ) as run:
                await self._stream_nodes(run)
                return list(run.result.all_messages()) if run.result else history_before

        except UsageLimitExceeded:
            self._discard_pending_response()
            self._emit_error(
                f"Maximum consecutive calls ({max_consecutive_calls}) reached. "
                "Please rephrase your request."
            )
            return history_before

        except UnexpectedModelBehavior:
            # Raised when a tool exhausted its retry budget.
            self._discard_pending_response()
            self._emit_error(
                f"Maximum consecutive errors ({max_consecutive_errors}) reached. "
                "Please rephrase your request."
            )
            return history_before

    async def _stream_nodes(self, run: Any) -> None:
        """Walk the run's nodes, emitting the events of each.

        Args:
            run: The active agent run.
        """
        async for node in run:
            if Agent.is_model_request_node(node):
                self._pending_response = await self._stream_model_request(node, run)

            elif Agent.is_call_tools_node(node):
                await self._stream_tool_calls(node, run)
                self._flush_pending_response()

                if self._stop_after_function_success and self._function_success_seen:
                    # Sub-agents stop here: the parent reports their success, so there is no
                    # point asking the model for a closing message.
                    return

        self._flush_pending_response()

    def _flush_pending_response(self) -> None:
        """Emit the closing events of the response still awaiting them, if any."""
        if self._pending_response:
            pending_response = self._pending_response
            self._pending_response = None
            self._close_response(*pending_response)

    def _discard_pending_response(self) -> None:
        """Drop the closing events of a response the run never finished.

        Called on the terminal error paths only. The response awaiting its closing events is one
        whose tool calls were still being resolved when the run was aborted, so it never became an
        answer: closing it would hand the consumer a response it persists as a *complete* one,
        and a truncated answer presented as complete is worse than no answer, because nothing
        downstream can tell the two apart. Consumers drop the text deltas already emitted when
        they see the error event that follows.
        """
        self._pending_response = None
        self._current_response_id = ""

    async def _stream_model_request(self, node: Any, run: Any) -> tuple[str, str]:
        """Stream one model request, emitting its text deltas.

        Args:
            node: The pydantic-ai ``ModelRequestNode``.
            run: The active agent run, for its streaming context.

        Returns:
            Tuple of (response_id, accumulated_text) whose closing events are still pending.
        """
        response_id = str(uuid4())
        self._current_response_id = response_id
        self.emit(cast(T, ResponseCreatedEvent(response_id=response_id, agent_id=self._agent_id)))

        text = ""
        async with node.stream(run.ctx) as stream:
            async for event in stream:
                delta = self._text_delta_of(event)
                if delta:
                    text += delta
                    self.emit(
                        cast(
                            T,
                            TextDeltaEvent(
                                delta=delta, response_id=response_id, agent_id=self._agent_id
                            ),
                        )
                    )

        return response_id, text

    async def _stream_tool_calls(self, node: Any, run: Any) -> None:
        """Stream one tool-calling step, emitting a function call event per tool call.

        The tool bodies run inside this stream and emit their own events through
        :meth:`emit`, so their events land between the function call event and the closing
        events of the response, exactly as they did on the OpenAI Responses stream.

        Args:
            node: The pydantic-ai ``CallToolsNode``.
            run: The active agent run, for its streaming context.
        """
        async with node.stream(run.ctx) as stream:
            async for event in stream:
                if isinstance(event, FunctionToolCallEvent):
                    self.emit(
                        cast(
                            T,
                            FunctionCallEvent(
                                call_id=event.part.tool_call_id,
                                response_id=self._current_response_id,
                                function_name=event.part.tool_name,
                                arguments=event.part.args_as_dict(),
                                agent_id=self._agent_id,
                            ),
                        )
                    )

    def _close_response(self, response_id: str, text: str) -> None:
        """Emit the deferred closing events of a response.

        Args:
            response_id: The response being closed.
            text: The full text streamed for that response.
        """
        self.emit(
            cast(
                T,
                ResponseFullTextEvent(
                    response_id=response_id, text=text, agent_id=self._agent_id
                ),
            )
        )
        self.emit(
            cast(T, ResponseCompletedEvent(response_id=response_id, agent_id=self._agent_id))
        )
        self._current_response_id = ""

    def _emit_error(self, message: str) -> None:
        """Emit a terminal error event for the run.

        Args:
            message: The error message shown to the user.
        """
        self.emit(cast(T, ErrorEvent(message=message, agent_id=self._agent_id)))

    @staticmethod
    def _text_delta_of(event: Any) -> str | None:
        """Extract the text increment carried by a model stream event, if any.

        Args:
            event: A pydantic-ai model response stream event.

        Returns:
            The text increment, or None when the event carries no text.
        """
        if isinstance(event, PartStartEvent) and isinstance(event.part, TextPart):
            return event.part.content or None

        if isinstance(event, PartDeltaEvent) and isinstance(event.delta, TextPartDelta):
            return event.delta.content_delta or None

        return None
