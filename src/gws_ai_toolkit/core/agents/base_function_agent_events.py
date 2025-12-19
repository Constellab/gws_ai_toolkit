from typing import Annotated, Any, Literal

from gws_core import BaseModelDTO
from pydantic import Field


class UserQueryEventBase(BaseModelDTO):
    query: str
    agent_id: str

    def serialize(self) -> dict:
        return self.to_json_dict()

    @classmethod
    def deserialize(cls, data: dict, additional_info: Any) -> "UserQueryEventBase":
        return cls.from_json(data)


class UserQueryTextEvent(UserQueryEventBase):
    type: Literal["user_query"] = "user_query"


class ResponseEvent(BaseModelDTO):
    response_id: str
    agent_id: str


# Typed event classes with literal types and direct attributes
class TextDeltaEvent(ResponseEvent):
    type: Literal["text_delta"] = "text_delta"
    delta: str


# abstract base class for function result events
class FunctionEventBase(ResponseEvent):
    call_id: str


class FunctionSuccessEvent(FunctionEventBase):
    """Event triggered when the agent finished its job in success state

    Must be extended to specific the type attribute
    """

    function_response: str


class FunctionErrorEvent(FunctionEventBase):
    """Event triggered when the agent finished its job in error state"""

    type: Literal["function_error"] = "function_error"
    message: str
    stack_trace: str | None = None  # Optional stack trace for AI context, not shown to user


class ErrorEvent(BaseModelDTO):
    type: Literal["error"] = "error"
    message: str
    agent_id: str


class CodeEvent(FunctionEventBase):
    type: Literal["code"] = "code"
    code: str


class FunctionCallEvent(FunctionEventBase):
    type: Literal["function_call"] = "function_call"
    function_name: str
    arguments: dict[str, Any]


class ResponseCreatedEvent(ResponseEvent):
    type: Literal["response_created"] = "response_created"


class ResponseCompletedEvent(ResponseEvent):
    type: Literal["response_completed"] = "response_completed"


class ResponseFullTextEvent(ResponseEvent):
    type: Literal["response_full_text"] = "response_full_text"
    text: str


class CreateSubAgent(ResponseEvent):
    """Event trigger before calling a sub agent.
    The reponse_id is the reponse_id that led to agent creation
    this is useful to retrieve the sub agent id when using replay
    The agent_id is the sub agent id.

    Args:
        FunctionSuccessEvent (_type_): _description_
    """

    type: Literal["create_sub_agent"] = "create_sub_agent"


class SubAgentSuccess(FunctionSuccessEvent):
    type: Literal["sub_agent_success"] = "sub_agent_success"


# Union type for all events
BaseFunctionAgentEvent = (
    TextDeltaEvent
    | FunctionErrorEvent
    | ErrorEvent
    | ResponseCreatedEvent
    | ResponseCompletedEvent
    | CodeEvent
    | FunctionCallEvent
    | ResponseFullTextEvent
)

# Type for events that can involve sub-agents
BaseFunctionWithSubAgentEvent = Annotated[
    TextDeltaEvent
    | FunctionErrorEvent
    | ErrorEvent
    | ResponseCreatedEvent
    | ResponseCompletedEvent
    | CodeEvent
    | FunctionCallEvent
    | ResponseFullTextEvent
    | CreateSubAgent
    | SubAgentSuccess,
    Field(discriminator="type"),
]

BaseFunctionWithSubAgentSerializableEvent = Annotated[
    FunctionCallEvent | ResponseFullTextEvent | CreateSubAgent | SubAgentSuccess,
    Field(discriminator="type"),
]
