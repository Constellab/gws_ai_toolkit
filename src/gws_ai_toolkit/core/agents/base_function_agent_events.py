from typing import Literal, Optional, Union

from gws_core import BaseModelDTO


# Typed event classes with literal types and direct attributes
class TextDeltaEvent(BaseModelDTO):
    type: Literal["text_delta"] = "text_delta"
    delta: str


# abstract base class for function result events
class FunctionResultEventBase(BaseModelDTO):
    call_id: str
    response_id: str


class FunctionSuccessEvent(FunctionResultEventBase):
    """Event triggered when the agent finished its job in success state

    Must be extended to specific the type attribute
    """
    function_response: str


class FunctionErrorEvent(FunctionResultEventBase):
    """Event triggered when the agent finished its job in error state
    """
    type: Literal["function_error"] = "function_error"
    message: str


class ErrorEvent(BaseModelDTO):
    type: Literal["error"] = "error"
    message: str
    error_type: str


class ResponseCreatedEvent(BaseModelDTO):
    type: Literal["response_created"] = "response_created"
    response_id: Optional[str]


class ResponseCompletedEvent(BaseModelDTO):
    type: Literal["response_completed"] = "response_completed"


# Union type for all events
BaseFunctionAgentEvent = Union[
    TextDeltaEvent,
    FunctionResultEventBase,
    FunctionErrorEvent,
    ErrorEvent,
    ResponseCreatedEvent,
    ResponseCompletedEvent
]
