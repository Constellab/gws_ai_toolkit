"""
Test file for env_generator_ai tasks: CondaEnvGeneratorAi and PipEnvGeneratorAi

Unlike ``_test_env_generator_ai.py`` (disabled, needs a real OPENAI_API_KEY and performs a
real conda/pipenv install), these tests drive the tasks through a scripted model and mock the
shell proxies, so no API call and no real environment installation is made.
"""

import os
from unittest import TestCase
from unittest.mock import patch

from gws_ai_toolkit.core.agents.env_generator_ai import CondaEnvGeneratorAi, PipEnvGeneratorAi
from gws_core import TaskRunner

from .agent_test_helper import SingleAgentScriptedModel, ToolCall

CONDA_ENV_YAML = (
    "name: myenv\nchannels:\n  - conda-forge\ndependencies:\n  - python=3.10\n  - numpy\n"
)
PIPFILE_CONTENT = '[packages]\nrequests = "*"\n'


# test_env_generator_ai
class TestEnvGeneratorAi(TestCase):
    """Drives the env generator tasks through a scripted model, so no API call and no real
    environment installation is made."""

    @patch("gws_ai_toolkit.core.agents.env_agent_ai.CondaShellProxy")
    @patch("gws_ai_toolkit.core.agents.base_pydantic_agent_ai.AiModelFactory.build")
    @patch.dict(os.environ, {"OPENAI_API_KEY": "test-key"})
    def test_conda_env_generator(self, mock_build, mock_shell_proxy_cls):
        """CondaEnvGeneratorAi accepts the 'openai:gpt-4' model string and produces the
        installed environment file content."""
        mock_shell_proxy = mock_shell_proxy_cls.return_value
        mock_shell_proxy.install_env.return_value = True
        mock_shell_proxy.get_env_dir_path.return_value = "/tmp/fake_env"

        scripted = SingleAgentScriptedModel(
            turns=[
                ToolCall("generate_conda_env_file", {"env_file_content": CONDA_ENV_YAML}),
                "Environment created.",
            ]
        )
        mock_build.return_value = scripted.build()

        runner = TaskRunner(
            task_type=CondaEnvGeneratorAi,
            params={
                "env_type": "conda",
                "user_prompt": "I need numpy",
                "existing_env_file": None,
            },
            inputs={},
        )
        outputs = runner.run()

        content = outputs["env_file"].read()
        self.assertEqual(content, CONDA_ENV_YAML)
        mock_shell_proxy.install_env.assert_called_once()

    @patch("gws_ai_toolkit.core.agents.env_agent_ai.PipShellProxy")
    @patch("gws_ai_toolkit.core.agents.base_pydantic_agent_ai.AiModelFactory.build")
    @patch.dict(os.environ, {"OPENAI_API_KEY": "test-key"})
    def test_pipenv_generator(self, mock_build, mock_shell_proxy_cls):
        """PipEnvGeneratorAi accepts the 'openai:gpt-4' model string and produces the
        installed Pipfile content."""
        mock_shell_proxy = mock_shell_proxy_cls.return_value
        mock_shell_proxy.install_env.return_value = True
        mock_shell_proxy.get_env_dir_path.return_value = "/tmp/fake_pipenv"

        scripted = SingleAgentScriptedModel(
            turns=[
                ToolCall(
                    "generate_pipenv_file",
                    {"env_file_content": PIPFILE_CONTENT, "python_version": "3.10"},
                ),
                "Pipfile created.",
            ]
        )
        mock_build.return_value = scripted.build()

        runner = TaskRunner(
            task_type=PipEnvGeneratorAi,
            params={
                "user_prompt": "I need requests",
                "existing_pipfile": None,
            },
            inputs={},
        )
        outputs = runner.run()

        content = outputs["env_file"].read()
        self.assertEqual(content, PIPFILE_CONTENT)
        mock_shell_proxy.install_env.assert_called_once()
