import json
import os
import tempfile
from typing import Generator, List, Optional

from gws_core import (BaseModelDTO, CondaShellProxy, MambaShellProxy,
                      MessageDispatcher, PipShellProxy)
from gws_core.core.classes.observer.message_observer import \
    BasicMessageObserver
from openai import OpenAI
from openai.types.responses import ResponseFunctionToolCall
from pydantic import Field
from typing_extensions import Literal

from .base_function_agent_ai import BaseFunctionAgentAi
from .env_agent_ai_events import (EnvAgentAiEvent, EnvFileGeneratedEvent,
                                  EnvInstallationStartedEvent,
                                  EnvInstallationSuccessEvent,
                                  FunctionErrorEvent)


class EnvConfig(BaseModelDTO):
    """Configuration for conda/mamba/pipenv environment file generation"""
    env_file_content: str = Field(
        description="Complete environment file content. For conda/mamba: environment.yml with proper YAML formatting including 'name', 'channels', and 'dependencies' sections. For pipenv: Pipfile with proper TOML formatting including '[[source]]', '[packages]', and '[requires]' sections.",
    )

    class Config:
        extra = "forbid"  # Prevent additional properties


class EnvAgentAi(BaseFunctionAgentAi[EnvAgentAiEvent]):
    """AI agent for generating and installing conda/mamba/pipenv environment files

    This agent helps users create working conda/mamba environment files or Pipfiles and
    automatically attempts to install them using CondaShellProxy, MambaShellProxy, or PipShellProxy.
    """

    _existing_env_content: Optional[str]
    _env_type: Literal["conda", "mamba", "pipenv"]

    def __init__(self,
                 openai_client: OpenAI,
                 model: str,
                 temperature: float,
                 env_type: Literal["conda", "mamba", "pipenv"] = "conda",
                 existing_env_content: Optional[str] = None,
                 skip_success_response: bool = False):
        """Initialize the EnvAgentAi

        Args:
            openai_client: OpenAI client instance
            model: Model name to use
            temperature: Temperature for generation
            env_type: Type of environment manager to use ("conda", "mamba", or "pipenv")
            existing_env_content: Optional existing environment file content (YAML for conda/mamba, Pipfile content for pipenv) that has installation problems
            message_dispatcher: Optional message dispatcher for logging
            skip_success_response: Whether to skip success response
        """
        super().__init__(openai_client, model, temperature, skip_success_response=skip_success_response)
        self._existing_env_content = existing_env_content
        self._env_type = env_type

    def _get_tools(self) -> List[dict]:
        """Get tools configuration for OpenAI"""
        if self._env_type == "pipenv":
            description = f"Generate a valid Pipfile for {self._env_type}. The file must be properly formatted TOML with '[[source]]', '[packages]', and '[requires]' sections."
        else:
            description = f"Generate a valid {self._env_type} environment.yml file. The file must be properly formatted YAML with 'name', 'channels', and 'dependencies' sections."

        return [
            {
                "type": "function",
                "name": "generate_conda_env_file",
                "description": description,
                "parameters": EnvConfig.model_json_schema()
            }
        ]

    def _handle_function_call(self, event_item: ResponseFunctionToolCall,
                              current_response_id: str) -> Generator[EnvAgentAiEvent, None, None]:
        """Handle output item done event"""
        function_args = event_item.arguments
        call_id = event_item.call_id

        if not function_args:
            yield FunctionErrorEvent(
                message="No function arguments provided for environment file generation.",
                call_id=call_id,
                response_id=current_response_id
            )
            return

        try:
            env_file_content = self._parse_env_file_content(function_args)

            # Emit the generated environment file event
            yield EnvFileGeneratedEvent(
                env_file_content=env_file_content,
                env_type=self._env_type,
                call_id=call_id,
                response_id=current_response_id,
                function_response="Successfully generated the environment file.",
            )

            # attempt to install the environment
            yield from self._install_environment(env_file_content, call_id, current_response_id)

            return

        except Exception as exec_error:
            yield FunctionErrorEvent(
                message=str(exec_error),
                call_id=call_id,
                response_id=current_response_id
            )
            return

    def _parse_env_file_content(self, arguments_str: str) -> str:
        """Parse and validate the environment file content from arguments

        Args:
            arguments_str: JSON string with function arguments

        Returns:
            The environment file content

        Raises:
            ValueError: If arguments are invalid
        """
        arguments = json.loads(arguments_str)
        env_file_content = arguments.get('env_file_content', '')

        if not env_file_content.strip():
            raise ValueError("No environment file content provided in function arguments")

        return env_file_content

    def _install_environment(self, env_file_content: str, call_id: str,
                             current_response_id: str) -> Generator[EnvAgentAiEvent, None, None]:
        """Attempt to install the generated environment

        Args:
            env_file_content: The environment file content to install
            call_id: The call ID for event tracking
            current_response_id: The current response ID

        Yields:
            Events related to the installation process
        """
        try:
            # Notify that installation is starting
            yield EnvInstallationStartedEvent(
                env_type=self._env_type,
                message=f"Starting {self._env_type} environment installation...",
                call_id=call_id,
                response_id=current_response_id,
                function_response="Installation started"
            )

            # Create a temporary directory for the environment
            temp_dir = tempfile.mkdtemp(prefix=f"{self._env_type}_env_")

            # Determine the config file name based on env type
            if self._env_type == "pipenv":
                config_file_name = "Pipfile"
            else:
                config_file_name = "environment.yml"

            env_file_path = os.path.join(temp_dir, config_file_name)

            # Write the environment file
            with open(env_file_path, 'w') as f:
                f.write(env_file_content)

            # Import the appropriate shell proxy
            message_dispatcher = MessageDispatcher(interval_time_merging_message=0, interval_time_dispatched_buffer=0)
            basic_observer = BasicMessageObserver()
            message_dispatcher.attach(basic_observer)

            if self._env_type == "mamba":
                shell_proxy = MambaShellProxy(
                    env_file_path=env_file_path,
                    working_dir=temp_dir,
                    message_dispatcher=message_dispatcher
                )
            elif self._env_type == "pipenv":
                shell_proxy = PipShellProxy(
                    env_file_path=env_file_path,
                    working_dir=temp_dir,
                    message_dispatcher=message_dispatcher
                )
            else:
                shell_proxy = CondaShellProxy(
                    env_file_path=env_file_path,
                    working_dir=temp_dir,
                    message_dispatcher=message_dispatcher
                )

            # Install the environment
            result = shell_proxy.install_env()

            if result:

                # Get the path to the installed environment
                env_path = shell_proxy.get_venv_dir_path()

                yield EnvInstallationSuccessEvent(
                    env_path=env_path,
                    env_file_content=env_file_content,
                    message=f"Successfully installed {self._env_type}",
                    call_id=call_id,
                    response_id=current_response_id,
                    function_response=f"Environment installed successfully"
                )
            else:
                yield EnvInstallationSuccessEvent(
                    env_path=env_path,
                    env_file_content=env_file_content,
                    message=f"The environment was already installed: {self._env_type}",
                    call_id=call_id,
                    response_id=current_response_id,
                    function_response=f"Environment installed successfully"
                )

        except Exception as install_error:
            error_message = str(install_error)

            yield FunctionErrorEvent(
                message=f"Failed to install environment: {error_message}",
                call_id=call_id,
                response_id=current_response_id
            )

    def _get_ai_instruction(self) -> str:
        """Create prompt for OpenAI with environment specifications

        Returns:
            Formatted prompt for OpenAI
        """
        existing_file_info = ""
        if self._existing_env_content:
            file_format = "Pipfile" if self._env_type == "pipenv" else "yaml"
            existing_file_info = f"""
## Existing Environment File (with installation problems):
```{file_format}
{self._existing_env_content}
```

The user has reported that this environment file has problems during installation. Please analyze it and fix any issues.
"""

        if self._env_type == "pipenv":
            return f"""You are an AI assistant specialized in creating pipenv Pipfile files.

{existing_file_info}

Your role is to help users create working Pipfile files based on their requirements. When users specify what packages they want to install, you should:

1. Generate a valid TOML-formatted Pipfile
2. Organize packages into [packages] and [dev-packages] sections appropriately
3. Specify package versions when requested by the user
4. Handle dependency conflicts intelligently
5. Follow best practices for pipenv environments
6. If an existing file was provided with errors, fix those errors

## Important Pipfile formatting rules:
- Use proper TOML syntax
- The file must include:
  - [[source]] section with PyPI or other package sources
  - [packages] section for production dependencies
  - [dev-packages] section for development dependencies (optional)
  - [requires] section for Python version
- Package versions should use "==" for exact versions, "*" for latest, or "~=" for compatible releases
- Use double quotes for all string values

## Example structure:
```toml
[[source]]
url = "https://pypi.org/simple"
verify_ssl = true
name = "pypi"

[packages]
numpy = "==1.21.0"
pandas = "*"
requests = "~=2.28.0"

[dev-packages]
pytest = "*"

[requires]
python_version = "3.9"
```

## Common issues to avoid:
- Don't use package version constraints that are too strict (can cause conflicts)
- Specify python_version in [requires] section
- Use appropriate version specifiers (==, >=, ~=, *)
- Consider platform compatibility
- Separate development dependencies from production dependencies

When generating the Pipfile:
- If the user mentions specific versions, use them
- If no version is specified, use "*" to get the latest compatible version
- Ensure the file is complete and ready to use with 'pipenv install'
- Do NOT include any markdown code block markers in the TOML content
- Provide ONLY the raw TOML content

Call the function only once per user request for a Pipfile.
"""

        else:
            return f"""You are an AI assistant specialized in creating {self._env_type} environment files (environment.yml).

{existing_file_info}

Your role is to help users create working {self._env_type} environment files based on their requirements. When users specify what packages they want to install, you should:

1. Generate a valid YAML environment.yml file
2. Include appropriate channels (defaults, conda-forge, etc.)
3. Specify package versions when requested by the user
4. Handle dependency conflicts intelligently
5. Follow best practices for {self._env_type} environments
6. If an existing file was provided with errors, fix those errors

## Important YAML formatting rules:
- Use proper YAML indentation (2 spaces)
- The file must include:
  - name: (environment name)
  - channels: (list of channels)
  - dependencies: (list of packages)
- Package versions should use '=' not ':' (e.g., numpy=1.21.0)
- Python version should be specified in dependencies
- Pip packages should be under a nested '- pip:' section if needed

## Example structure:
```yaml
name: myenv
channels:
  - defaults
  - conda-forge
dependencies:
  - python=3.9
  - numpy=1.21.0
  - pandas
  - pip:
    - requests==2.28.0
```

## Common issues to avoid:
- Don't use package version constraints that are too strict (can cause conflicts)
- Include python in dependencies
- Use appropriate channels for specialized packages
- Consider platform compatibility
- Avoid mixing packages from incompatible channels

When generating the environment file:
- If the user mentions specific versions, use them
- Do not provide a name for the environment
- If no version is specified, you can either omit the version or use a recent stable version
- Ensure the file is complete and ready to use with '{self._env_type} env create -f environment.yml'
- Do NOT include any markdown code block markers in the YAML content
- Provide ONLY the raw YAML content

Call the function only once per user request for an environment file.
"""


# Backward compatibility alias
CondaEnvAgentAi = EnvAgentAi
