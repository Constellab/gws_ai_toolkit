from typing import Generic, TypeVar

from gws_core import BaseModelDTO
from pydantic import TypeAdapter

from ..base_function_agent_events import (
    BaseFunctionWithSubAgentEvent,
    CreateSubAgent,
    ResponseCompletedEvent,
    ResponseCreatedEvent,
    ResponseEvent,
    UserQueryEventBase,
)

T = TypeVar("T", bound=BaseModelDTO)


class AgentEventList(Generic[T]):
    """Manages a list of agent events with utility methods for querying and serialization"""

    _events: list[T]

    def __init__(self, events: list[T] | None = None):
        self._events: list[T] = events if events is not None else []

    def append(self, event: T) -> None:
        """Add an event to the list"""
        self._events.append(event)

    def get_all(self) -> list[T]:
        """Get all events"""
        return self._events

    def last_event(self, event_type: type[T]) -> T | None:
        """Get the last event of a specific type"""
        for event in reversed(self._events):
            if isinstance(event, event_type):
                return event
        return None

    def get_events_by_response_id(self, response_id: str) -> list[T]:
        """Get all events for a specific response ID"""
        return [
            event for event in self._events if getattr(event, "response_id", None) == response_id
        ]

    def get_agent_and_sub_agents_events(self, agent_id: str) -> list[T]:
        """Get all events for a specific agent and its sub-agents.

        This method loops through all emitted events and collects events that belong to the specified agent.
        When it encounters a ResponseCreatedEvent with the matching agent_id, it captures all subsequent
        events until it reaches the corresponding ResponseCompletedEvent for that response, even if those
        events belong to sub-agents (different agent_ids).

        This works because events are emmited in order, so all events related to a response are grouped together.
        Example:
            - ResponseCreatedEvent (agent_id=A, response_id=R1)
            - FunctionCallEvent (agent_id=A, response_id=R1)
            - ResponseCreatedEvent (agent_id=B, response_id=R2)  # sub-agent event
            - FunctionCallEvent (agent_id=B, response_id=R1)  # sub-agent event
            - ResponseCompletedEvent (agent_id=B, response_id=R2)  # sub-agent event
            - ResponseCompletedEvent (agent_id=A, response_id=R1)


        Args:
            agent_id: The ID of the agent to get events for

        Returns:
            List of events for the specified agent and any sub-agents involved in its responses
        """
        agent_events = []
        active_response_ids: set[str] = set()  # Track response IDs from the target agent

        for event in self._events:
            event_agent_id: str | None = None
            event_response_id: str | None = None

            if isinstance(event, ResponseEvent):
                event_agent_id = event.agent_id
                event_response_id = event.response_id

            if isinstance(event, UserQueryEventBase):
                event_agent_id = event.agent_id

            # Check if this is a ResponseCreatedEvent from our target agent
            if isinstance(event, ResponseCreatedEvent) and event_agent_id == agent_id:
                # Start tracking this response - we want all events until it completes
                active_response_ids.add(event_response_id)
                agent_events.append(event)
                continue

            # Check if this is a ResponseCompletedEvent for one of our tracked responses
            if (
                isinstance(event, ResponseCompletedEvent)
                and event_response_id in active_response_ids
            ):
                agent_events.append(event)
                # Stop tracking this response
                active_response_ids.discard(event_response_id)
                continue

            # If we're currently tracking a response, add all events regardless of agent_id
            # This captures sub-agent events that occur during the main agent's response
            if len(active_response_ids) > 0:
                agent_events.append(event)
                continue

            # Always add events that belong directly to the target agent
            if event_agent_id == agent_id:
                agent_events.append(event)

        return agent_events

    def find_create_sub_agent_event(self, response_id: str) -> CreateSubAgent | None:
        """Find the CreateSubAgent event for a given response ID.

        Args:
            response_id: The response ID to search for
        Returns:
            The CreateSubAgent event if found, else None
        """
        for event in self._events:
            if isinstance(event, CreateSubAgent) and event.response_id == response_id:
                return event
        return None

    @staticmethod
    def from_json_list(json_list: list[dict]) -> "AgentEventList[T]":
        """Create an AgentEventList from a list of JSON dicts.

        Args:
            json_list: List of event JSON dicts
        Returns:
            AgentEventList instance
        """
        adapter = TypeAdapter(BaseFunctionWithSubAgentEvent)

        event_objects = [adapter.validate_python(m) for m in json_list]
        return AgentEventList[T](event_objects)
