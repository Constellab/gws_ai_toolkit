import asyncio
import json
from abc import ABC, abstractmethod
from collections.abc import AsyncGenerator, Generator
from typing import Any, Generic, TypeVar, cast
from uuid import uuid4

from gws_core import BaseModelDTO
from openai import OpenAI
from openai.types.responses import ResponseFunctionToolCall, ResponseOutputItemDoneEvent

from gws_ai_toolkit.core.agents.table.agent_event_list import AgentEventList

from .base_function_agent_events import (
    CreateSubAgent,
    ErrorEvent,
    FunctionCallEvent,
    FunctionErrorEvent,
    FunctionEventBase,
    FunctionSuccessEvent,
    ResponseCompletedEvent,
    ResponseCreatedEvent,
    ResponseEvent,
    ResponseFullTextEvent,
    SubAgentSuccess,
    TextDeltaEvent,
    UserQueryEventBase,
)

T = TypeVar("T", bound=BaseModelDTO)
U = TypeVar("U", bound=UserQueryEventBase)


class BaseFunctionAgentAi(ABC, Generic[T, U]):
    """Base class for AI agents that interact with OpenAI streaming API to call functions"""

    MAX_CONSECUTIVE_ERRORS = 5
    MAX_CONSECUTIVE_CALLS = 10

    # We only store the open ai api key, not the client itself
    # because this is used in reflex and reflex can't pickle open_ai client
    id: str
    _openai_api_key: str
    _model: str
    _temperature: float
    _event_list: AgentEventList[T]
    _skip_success_response: bool
    _replay_mode: bool = False
    _replayed_events: AgentEventList[T] | None = None

    def __init__(
        self,
        openai_api_key: str,
        model: str,
        temperature: float,
        skip_success_response: bool = False,
    ):
        self.id = str(uuid4())
        self._openai_api_key = openai_api_key
        self._model = model
        self._temperature = temperature
        self._event_list = AgentEventList[T]()
        self._success_inputs = None
        self._skip_success_response = skip_success_response

    def _get_openai_client(self) -> OpenAI:
        """Create and return OpenAI client on-demand.

        This avoids storing the client which contains unpicklable objects like SSLContext.
        """
        return OpenAI(api_key=self._openai_api_key)

    async def call_agent_async(
        self,
        user_query: U,
    ) -> AsyncGenerator[T, None]:
        """Asynchronous wrapper for call_agent to collect all events into a list

        Args:
            user_query: User's request
        Returns:
            List of all events emitted during generation
        """
        loop = asyncio.get_event_loop()
        for event in await loop.run_in_executor(None, lambda: list(self.call_agent(user_query))):
            yield event

    def call_agent(
        self,
        user_query: U,
    ) -> Generator[T, None, None]:
        """Generate response with streaming events

        Args:
            user_query: User's request
            new_table_name: Optional new name for the transformed table

        Yields:
            PlotAgentEvent: Stream of events during generation
        """
        consecutive_error_count = 0
        consecutive_call_count = 0

        messages = [{"role": "user", "content": [{"type": "input_text", "text": user_query.query}]}]
        user_event = cast(T, user_query)
        self._event_list.append(user_event)
        yield user_event

        # Main generation loop - replace recursion with iteration
        while (
            consecutive_error_count < self.MAX_CONSECUTIVE_ERRORS
            and consecutive_call_count < self.MAX_CONSECUTIVE_CALLS
        ):
            consecutive_call_count += 1

            success_event: FunctionSuccessEvent | None = None
            error_event: FunctionErrorEvent | None = None

            # Generate events for this attempt
            for event in self._generate_stream_internal(messages, user_query):
                self._event_list.append(event)
                yield event

                # we check the function result events to determine if we need to continue
                # we only filter the events for the current response_id
                # this is useful to ignore events from sub agents in case of delegation
                if isinstance(event, FunctionEventBase) and event.agent_id == self.id:
                    if isinstance(event, FunctionErrorEvent):
                        error_event = event

                    if isinstance(event, FunctionSuccessEvent) and not self._skip_success_response:
                        # this is a successful function call
                        success_event = event

            # If function was successfully called, prepare success response
            if success_event:
                messages = [
                    {
                        "type": "function_call_output",
                        "call_id": success_event.call_id,
                        "output": json.dumps({"Result": success_event.function_response}),
                    }
                ]
                continue

            # If there was an error during the function call, prepare error message for next iteration
            if error_event:
                consecutive_error_count += 1
                if not error_event.call_id:
                    # If no call_id, we cannot proceed with function call output
                    break
                messages = [
                    {
                        "type": "function_call_output",
                        "call_id": error_event.call_id,
                        "output": json.dumps({"Result": error_event.message}),
                    },
                    {
                        "role": "user",
                        "content": [{"type": "input_text", "text": "Can you fix the code?"}],
                    },
                ]
                continue

            # If there were no function call and no error, we are done
            if not success_event and not error_event:
                break

        if consecutive_error_count >= self.MAX_CONSECUTIVE_ERRORS:
            error = cast(
                T,
                ErrorEvent(
                    message=f"Maximum consecutive errors ({self.MAX_CONSECUTIVE_ERRORS}) reached. Please rephrase your request.",
                    agent_id=self.id,
                ),
            )
            self._event_list.append(error)
            yield error

        if consecutive_call_count >= self.MAX_CONSECUTIVE_CALLS:
            error = cast(
                T,
                ErrorEvent(
                    message=f"Maximum consecutive calls ({self.MAX_CONSECUTIVE_CALLS}) reached. Please rephrase your request.",
                    agent_id=self.id,
                ),
            )
            self._event_list.append(error)
            yield error

    def _generate_stream_internal(
        self,
        input_messages: list[dict],
        user_query: U,
    ) -> Generator[T, None, None]:
        """Internal method for generation with streaming"""

        # Create prompt with table metadata
        prompt = self._get_ai_instruction(user_query)

        # Define tools for OpenAI
        tools = self._get_tools()

        current_response_id: str = ""
        text_response: str = ""

        # Get OpenAI client (creates new instance on-demand)
        openai_client = self._get_openai_client()

        # Stream OpenAI response directly
        with openai_client.responses.stream(
            model=self._model,
            instructions=prompt,
            input=input_messages,
            temperature=self._temperature,
            previous_response_id=self._get_and_check_last_response_id(),
            tools=tools,
            parallel_tool_calls=False,  # Disable parallel function calls for iterative processing
        ) as stream:
            # Process streaming events
            for event in stream:
                # Yield streaming events to consumer
                if event.type == "response.output_text.delta":
                    text_response = (text_response or "") + event.delta
                    yield cast(
                        T,
                        TextDeltaEvent(
                            delta=event.delta, response_id=current_response_id, agent_id=self.id
                        ),
                    )

                elif event.type == "response.created":
                    text_response = ""
                    current_response_id = event.response.id
                    yield cast(
                        T, ResponseCreatedEvent(response_id=current_response_id, agent_id=self.id)
                    )
                elif event.type == "response.completed":
                    # If the response was a text response containing only text deltas, we can yield the full text event here
                    if text_response is not None:
                        yield cast(
                            T,
                            ResponseFullTextEvent(
                                response_id=event.response.id, text=text_response, agent_id=self.id
                            ),
                        )
                    yield cast(
                        T, ResponseCompletedEvent(response_id=event.response.id, agent_id=self.id)
                    )
                    text_response = ""
                    current_response_id = ""
                elif event.type == "response.output_item.done":
                    yield from self._handle_response_output_item_done_event(
                        event, current_response_id, user_query
                    )

    def _get_and_check_last_response_id(self) -> str | None:
        """Get and check that the current response ID is set

        Returns:
            Current response ID

        Raises:
            ValueError: If the current response ID is not set
        """
        for event in reversed(self._event_list.get_all()):
            if isinstance(event, ResponseEvent):
                return event.response_id

        return None

    def _handle_response_output_item_done_event(
        self, event: ResponseOutputItemDoneEvent, current_response_id: str, user_query: U
    ) -> Generator[T, None, None]:
        """Handle output item done event - can be overridden by subclasses

        Args:
            event: The output item done event
            current_response_id: Current response ID

        Returns:
            Optional[PlotAgentEvent]: Event generated from handling the output, or None
        """
        if not isinstance(event, ResponseOutputItemDoneEvent) or not isinstance(
            event.item, ResponseFunctionToolCall
        ):
            return

        event_items = cast(ResponseFunctionToolCall, event.item)

        arguments = json.loads(event_items.arguments)

        function_call_event = FunctionCallEvent(
            call_id=event_items.call_id,
            response_id=current_response_id,
            function_name=event_items.name,
            arguments=arguments,
            agent_id=self.id,
        )

        yield cast(T, function_call_event)

        yield from self._handle_function_call(function_call_event, user_query)

    @abstractmethod
    def _handle_function_call(
        self, function_call_event: FunctionCallEvent, user_query: U
    ) -> Generator[T, None, None]:
        """Handle function call event - must be implemented by subclasses

        Args:
            function_call_event: The function call event containing call_id, response_id, function_name, and arguments
            user_query: The user query event associated with the function call

        Yields:
            T: Events generated from handling the function call
        """

    @abstractmethod
    def _get_ai_instruction(self, user_query: U) -> str:
        """Create prompt for OpenAI - must be implemented by subclasses

        Returns:
            Formatted prompt for OpenAI
        """

    @abstractmethod
    def _get_tools(self) -> list[dict]:
        """Get tools configuration for OpenAI - must be implemented by subclasses

        Returns:
            List of tool configurations
        """

    def get_emitted_events(self) -> list[T]:
        """Get all events emitted during the last generation"""
        return self._event_list.get_all()

    def replay_events(
        self, events: list[T], user_query: U | None = None
    ) -> Generator[T, None, None]:
        """Replay a list of events by yielding them one by one

        This is useful for replaying previously emitted events without
        calling the agent again. The events are yielded in order.

        Args:
            events: List of events to replay

        Yields:
            T: Each event from the input list
        """
        self._replay_mode = True

        events_list: list[T]
        events_list = cast(list[T], [user_query]) + events if user_query is not None else events

        self._replayed_events = AgentEventList(events_list)
        last_user_query: U | None = None
        for event in events_list:
            if isinstance(event, UserQueryEventBase):
                self._event_list.append(event)
                yield event
                last_user_query = cast(U, event)

            if isinstance(event, FunctionCallEvent):
                self._event_list.append(event)
                yield event
                if not last_user_query:
                    raise ValueError("No user query found before function call event")
                for sub_event in self._handle_function_call(event, last_user_query):
                    self._event_list.append(sub_event)
                    yield sub_event

    def call_sub_agent(
        self,
        sub_agent: "BaseFunctionAgentAi",
        user_query: UserQueryEventBase,
        parent_response_id: str,
        parent_call_id: str,
        parent_agent_id: str,
    ) -> Generator[Any, None, None]:
        """Call a sub-agent and yield its events directly

        Args:
            sub_agent: The sub-agent to call
            user_request: User's request to pass to the sub-agent

        Yields:
            T: Events emitted by the sub-agent
        """
        # emit the CreateSubAgent event
        # This event is used to track sub-agent calls in the main agent's event list
        # This is useful for replaying events later
        yield CreateSubAgent(
            response_id=parent_response_id,
            agent_id=sub_agent.id,
        )

        events: Generator[Any, None, None]

        if self._replay_mode:
            # find the CreateSubAgent event with the matching response_id
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
            # insert the user query event at the beginning of the sub-agent events
            # it is required by the replay_events
            events = sub_agent.replay_events(sub_agent_events, user_query)
        else:
            if user_query is None:
                raise ValueError("user_query must be provided when not in replay mode")
            events = sub_agent.call_agent(user_query)

        success_event: FunctionSuccessEvent | None = None
        for event in events:
            yield event

            if isinstance(event, FunctionSuccessEvent):
                success_event = event

        if success_event:
            # emit event at parent level to indicate sub-agent success
            yield SubAgentSuccess(
                call_id=parent_call_id,
                response_id=parent_response_id,
                function_response=f"{success_event.function_response} Continue with next steps if needed.",
                agent_id=parent_agent_id,
            )

    def get_last_user_query(self) -> U | None:
        """Get the last user query event"""
        return cast(U, self._event_list.last_event(cast(type[T], UserQueryEventBase)))

    def get_model(self) -> str:
        """Get the model used by the agent"""
        return self._model

    def get_temperature(self) -> float:
        """Get the temperature used by the agent"""
        return self._temperature

    def get_events(self) -> AgentEventList[T]:
        """Get all events emitted during the last generation"""
        return self._event_list
