import json
from abc import ABC, abstractmethod
from typing import Generator, Generic, List, Optional, TypeVar, cast

from gws_core import BaseModelDTO
from openai import OpenAI
from openai.types.responses import (ResponseFunctionToolCall,
                                    ResponseOutputItemDoneEvent)

from .base_function_agent_events import (ErrorEvent, FunctionResultEventBase,
                                         ResponseCompletedEvent,
                                         ResponseCreatedEvent, TextDeltaEvent)

T = TypeVar('T', bound=BaseModelDTO)


class BaseFunctionAgentAi(ABC, Generic[T]):
    """Base class for AI agents that interact with OpenAI streaming API to call functions

    """

    MAX_CONSECUTIVE_ERRORS = 5
    MAX_CONSECUTIVE_CALLS = 10

    _openai_client: OpenAI
    _model: str
    _temperature: float
    _previous_response_id: Optional[str]
    _emitted_events: List[T]
    _new_table_name: Optional[str]

    def __init__(self, openai_client: OpenAI,
                 model: str,
                 temperature: float):
        self._openai_client = openai_client
        self._model = model
        self._temperature = temperature
        self._previous_response_id = None
        self._emitted_events = []
        self._success_inputs = None
        self._new_table_name = None

    def call_agent(
        self,
        user_query: str,
        new_table_name: Optional[str] = None,
    ) -> Generator[T, None, None]:
        """Generate response with streaming events

        Args:
            user_query: User's request
            new_table_name: Optional new name for the transformed table

        Yields:
            PlotAgentEvent: Stream of events during generation
        """
        self._new_table_name = new_table_name
        consecutive_error_count = 0
        consecutive_call_count = 0

        messages = [{"role": "user", "content": [{"type": "input_text", "text": user_query}]}]

        # Main generation loop - replace recursion with iteration
        while (consecutive_error_count < self.MAX_CONSECUTIVE_ERRORS and
               consecutive_call_count < self.MAX_CONSECUTIVE_CALLS):
            consecutive_call_count += 1

            success_function_call_id: str | None = None
            error_event: ErrorEvent | None = None

            # Generate events for this attempt
            for event in self._generate_stream_internal(messages):
                self._emitted_events.append(event)
                yield event

                if isinstance(event, FunctionResultEventBase):
                    # Success event was generated
                    success_function_call_id = event.call_id

                elif isinstance(event, ErrorEvent):
                    error_event = event

            # If function was successfully called, prepare success response
            if success_function_call_id:
                messages = [{
                    "type": "function_call_output",
                    "call_id": success_function_call_id,
                    "output": json.dumps(self._get_success_response())
                }]
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
                        "output": json.dumps(self._get_error_response(error_event.message))
                    },
                    {"role": "user", "content": [{"type": "input_text", "text": "Can you fix the code?"}]}
                ]
                continue

            # If there were no function call and no error, we are done
            if not success_function_call_id and not error_event:
                break

        if consecutive_error_count >= self.MAX_CONSECUTIVE_ERRORS:
            yield cast(T, ErrorEvent(
                message=f"Maximum consecutive errors ({self.MAX_CONSECUTIVE_ERRORS}) reached",
                code=None,
                error_type="max_errors_reached",
            ))

        if consecutive_call_count >= self.MAX_CONSECUTIVE_CALLS:
            yield cast(T, ErrorEvent(
                message=f"Maximum consecutive calls ({self.MAX_CONSECUTIVE_CALLS}) reached",
                code=None,
                error_type="max_calls_reached",
            ))

    def _generate_stream_internal(
        self,
        input_messages: List[dict],
    ) -> Generator[T, None, None]:
        """Internal method for generation with streaming"""

        # Create prompt with table metadata
        prompt = self._get_ai_instruction()

        # Define tools for OpenAI
        tools = self._get_tools()

        current_response_id: str = ""

        # Stream OpenAI response directly
        with self._openai_client.responses.stream(
            model=self._model,
            instructions=prompt,
            input=input_messages,
            temperature=self._temperature,
            previous_response_id=self._previous_response_id,
            tools=tools
        ) as stream:

            # Process streaming events
            for event in stream:
                # Yield streaming events to consumer
                if event.type == "response.output_text.delta":
                    yield cast(T, TextDeltaEvent(delta=event.delta))

                elif event.type == "response.created":
                    current_response_id = event.response.id
                    yield cast(T, ResponseCreatedEvent(response_id=current_response_id))
                elif event.type == "response.completed":
                    self._previous_response_id = event.response.id
                    yield cast(T, ResponseCompletedEvent())
                elif event.type == "response.output_item.done":
                    for item_event in self._handle_response_output_item_done_event(event, current_response_id):
                        yield item_event

    def _handle_response_output_item_done_event(self, event: ResponseOutputItemDoneEvent,
                                                current_response_id: str) -> Generator[T, None, None]:
        """Handle output item done event - can be overridden by subclasses

        Args:
            event: The output item done event
            current_response_id: Current response ID

        Returns:
            Optional[PlotAgentEvent]: Event generated from handling the output, or None
        """
        if not isinstance(event, ResponseOutputItemDoneEvent) or \
                not isinstance(event.item, ResponseFunctionToolCall):
            return

        yield from self._handle_function_call(event.item, current_response_id)

    @abstractmethod
    def _handle_function_call(self, event_item: ResponseFunctionToolCall,
                              current_response_id: str) -> Generator[T, None, None]:
        """Handle output item done event - must be implemented by subclasses

        Args:
            event: The output item done event
            current_response_id: Current response ID

        Yields:
            PlotAgentEvent: Events generated from handling the output
        """

    @abstractmethod
    def _get_ai_instruction(self) -> str:
        """Create prompt for OpenAI - must be implemented by subclasses

        Returns:
            Formatted prompt for OpenAI
        """

    @abstractmethod
    def _get_tools(self) -> List[dict]:
        """Get tools configuration for OpenAI - must be implemented by subclasses

        Returns:
            List of tool configurations
        """

    def _get_success_response(self) -> dict:
        """Get success response for function call output"""
        return {"Result": "Successfully completed the task."}

    def _get_error_response(self, error_message: str) -> dict:
        """Get error response for function call output"""
        return {"Result": f"Error: {error_message}"}

    def get_emitted_events(self) -> List[T]:
        """Get all events emitted during the last generation"""
        return self._emitted_events
