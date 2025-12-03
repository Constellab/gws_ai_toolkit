from typing import Literal

from gws_ai_toolkit.core.agents.base_function_agent_events import (
    BaseFunctionAgentEvent,
    FunctionEventBase,
    FunctionSuccessEvent,
    UserQueryTextEvent,
)

# Typed event classes with literal types and direct attributes


class EnvFileGeneratedEvent(FunctionEventBase):
    type: Literal["env_file_generated"] = "env_file_generated"
    env_file_content: str  # The generated environment.yml or environment.yaml content
    env_type: Literal["conda", "mamba", "pipenv"]  # The type of environment


class EnvInstallationStartedEvent(FunctionEventBase):
    type: Literal["env_installation_started"] = "env_installation_started"
    env_type: Literal["conda", "mamba", "pipenv"]
    message: str


class EnvInstallationSuccessEvent(FunctionSuccessEvent):
    type: Literal["env_installation_success"] = "env_installation_success"
    env_path: str  # Path to the installed environment
    message: str
    env_file_content: str


# Union type for all events
EnvAgentAiEvent = (
    BaseFunctionAgentEvent
    | EnvFileGeneratedEvent
    | EnvInstallationStartedEvent
    | EnvInstallationSuccessEvent
    | UserQueryTextEvent
)
