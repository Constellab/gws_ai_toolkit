from typing import Literal, Union

from gws_ai_toolkit.core.agents.base_function_agent_events import (
    ErrorEvent, FunctionErrorEvent, FunctionSuccessEvent,
    ResponseCompletedEvent, ResponseCreatedEvent, TextDeltaEvent)
from gws_core import BaseModelDTO

# Typed event classes with literal types and direct attributes


class EnvFileGeneratedEvent(BaseModelDTO):
    type: Literal["env_file_generated"] = "env_file_generated"
    env_file_content: str  # The generated environment.yml or environment.yaml content
    env_type: Literal["conda", "mamba"]  # The type of environment


class EnvInstallationStartedEvent(BaseModelDTO):
    type: Literal["env_installation_started"] = "env_installation_started"
    env_type: Literal["conda", "mamba"]
    message: str


class EnvInstallationSuccessEvent(FunctionSuccessEvent):
    type: Literal["env_installation_success"] = "env_installation_success"
    env_path: str  # Path to the installed environment
    message: str
    env_file_content: str


# Union type for all events
EnvAgentAiEvent = Union[
    TextDeltaEvent,
    EnvFileGeneratedEvent,
    EnvInstallationStartedEvent,
    EnvInstallationSuccessEvent,
    FunctionErrorEvent,
    ErrorEvent,
    ResponseCreatedEvent,
    ResponseCompletedEvent
]
