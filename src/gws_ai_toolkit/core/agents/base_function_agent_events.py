from typing import Literal, Optional, Union

from gws_core import BaseModelDTO


# Typed event classes with literal types and direct attributes
class TextDeltaEvent(BaseModelDTO):
    type: Literal["text_delta"] = "text_delta"
    delta: str


# abstract base class for function result events
class FunctionResultEventBase(BaseModelDTO):
    code: str
    call_id: Optional[str]
    response_id: Optional[str]


class ErrorEvent(BaseModelDTO):
    type: Literal["error"] = "error"
    message: str
    code: Optional[str]
    error_type: str
    call_id: str | None = None


class ResponseCreatedEvent(BaseModelDTO):
    type: Literal["response_created"] = "response_created"
    response_id: Optional[str]


class ResponseCompletedEvent(BaseModelDTO):
    type: Literal["response_completed"] = "response_completed"


# Union type for all events
BaseFunctionAgentEvent = Union[
    TextDeltaEvent,
    FunctionResultEventBase,
    ErrorEvent,
    ResponseCreatedEvent,
    ResponseCompletedEvent
]
