from unittest.mock import MagicMock, patch

from gws_ai_toolkit.core.agents.base_function_agent_events import (
    FunctionErrorEvent,
    UserQueryTextEvent,
)
from gws_ai_toolkit.core.agents.env_agent_ai import EnvAgentAi
from gws_ai_toolkit.core.agents.env_agent_ai_events import (
    EnvFileGeneratedEvent,
    EnvInstallationStartedEvent,
    EnvInstallationSuccessEvent,
)
from gws_core import BaseTestCase

from .agent_test_helper import ScriptedAnswer, SingleAgentScriptedModel, ToolCall

CONDA_ENV_YAML = (
    "name: myenv\nchannels:\n  - conda-forge\ndependencies:\n  - python=3.10\n  - numpy\n"
)
FIXED_ENV_YAML = (
    "name: myenv\nchannels:\n  - conda-forge\ndependencies:\n  - python=3.10\n  - numpy=1.24\n"
)
PIPFILE_CONTENT = '[packages]\nrequests = "*"\n'


# test_env_agent_ai
class TestEnvAgentAi(BaseTestCase):
    """Drives EnvAgentAi through a scripted model, so no API call and no real environment
    installation is made."""

    def _build_agent(
        self, turns: list[ScriptedAnswer], **kwargs
    ) -> tuple[EnvAgentAi, SingleAgentScriptedModel]:
        """Build an agent backed by a scripted model.

        Args:
            turns: Turns to replay.
            kwargs: Extra constructor arguments for EnvAgentAi (e.g. env_type).

        Returns:
            Tuple of (agent, scripted model).
        """
        scripted = SingleAgentScriptedModel(turns=turns)
        agent = EnvAgentAi(
            openai_api_key=None,
            model=scripted.build(),
            temperature=0.1,
            **kwargs,
        )
        return agent, scripted

    @patch("gws_ai_toolkit.core.agents.env_agent_ai.CondaShellProxy")
    def test_generate_and_install_conda_env(self, mock_shell_proxy_cls):
        """A generated environment file is installed and reported as a success."""
        mock_shell_proxy = mock_shell_proxy_cls.return_value
        mock_shell_proxy.install_env.return_value = True
        mock_shell_proxy.get_env_dir_path.return_value = "/tmp/fake_env"

        agent, _ = self._build_agent(
            [
                ToolCall("generate_conda_env_file", {"env_file_content": CONDA_ENV_YAML}),
                "Environment created.",
            ]
        )

        user_query = UserQueryTextEvent(query="I need numpy", agent_id=agent.id)
        events = list(agent.call_agent(user_query))

        generated = [e for e in events if isinstance(e, EnvFileGeneratedEvent)]
        self.assertEqual(len(generated), 1)
        self.assertEqual(generated[0].env_file_content, CONDA_ENV_YAML)

        started = [e for e in events if isinstance(e, EnvInstallationStartedEvent)]
        self.assertEqual(len(started), 1)

        success = [e for e in events if isinstance(e, EnvInstallationSuccessEvent)]
        self.assertEqual(len(success), 1)
        self.assertEqual(success[0].env_path, "/tmp/fake_env")

        mock_shell_proxy.install_env.assert_called_once()

    @patch("gws_ai_toolkit.core.agents.env_agent_ai.CondaShellProxy")
    def test_installation_error_is_retried_then_succeeds(self, mock_shell_proxy_cls):
        """A failing installation produces an error event, then the model corrects itself."""
        failing_proxy = MagicMock()
        failing_proxy.install_env.side_effect = RuntimeError("solver conflict")
        succeeding_proxy = MagicMock()
        succeeding_proxy.install_env.return_value = True
        succeeding_proxy.get_env_dir_path.return_value = "/tmp/fake_env"
        mock_shell_proxy_cls.side_effect = [failing_proxy, succeeding_proxy]

        agent, _ = self._build_agent(
            [
                ToolCall("generate_conda_env_file", {"env_file_content": CONDA_ENV_YAML}),
                ToolCall("generate_conda_env_file", {"env_file_content": FIXED_ENV_YAML}),
                "Fixed and installed.",
            ]
        )

        user_query = UserQueryTextEvent(query="I need numpy", agent_id=agent.id)
        events = list(agent.call_agent(user_query))

        errors = [e for e in events if isinstance(e, FunctionErrorEvent)]
        self.assertEqual(len(errors), 1)
        self.assertIn("solver conflict", errors[0].message)

        success = [e for e in events if isinstance(e, EnvInstallationSuccessEvent)]
        self.assertEqual(len(success), 1)
        self.assertEqual(success[0].env_file_content, FIXED_ENV_YAML)

    @patch("gws_ai_toolkit.core.agents.env_agent_ai.PipShellProxy")
    def test_pipenv_generation(self, mock_shell_proxy_cls):
        """The pipenv env type dispatches to PipShellProxy and reports a success."""
        mock_shell_proxy = mock_shell_proxy_cls.return_value
        mock_shell_proxy.install_env.return_value = True
        mock_shell_proxy.get_env_dir_path.return_value = "/tmp/fake_pipenv"

        agent, _ = self._build_agent(
            [
                ToolCall(
                    "generate_pipenv_file",
                    {"env_file_content": PIPFILE_CONTENT, "python_version": "3.10"},
                ),
                "Pipfile created.",
            ],
            env_type="pipenv",
        )

        user_query = UserQueryTextEvent(query="I need requests", agent_id=agent.id)
        events = list(agent.call_agent(user_query))

        success = [e for e in events if isinstance(e, EnvInstallationSuccessEvent)]
        self.assertEqual(len(success), 1)
        mock_shell_proxy_cls.assert_called_once()

    def test_missing_env_file_content_reports_an_error(self):
        """An empty generated file is reported as an error rather than attempting installation."""
        agent, _ = self._build_agent(
            [
                ToolCall("generate_conda_env_file", {"env_file_content": ""}),
                "I need more details.",
            ]
        )

        user_query = UserQueryTextEvent(query="Make me an env", agent_id=agent.id)
        events = list(agent.call_agent(user_query))

        errors = [e for e in events if e.type == "function_error"]
        self.assertEqual(len(errors), 1)

    def test_model_is_configured_as_a_provider_model_string(self):
        """The agent reports its model as a 'provider:model' string."""
        agent = EnvAgentAi(openai_api_key="key", model="openai:gpt-4o", temperature=0.2)
        self.assertEqual(agent.get_model(), "openai:gpt-4o")
        self.assertEqual(agent.get_temperature(), 0.2)

        # A bare model name stays readable, for configurations saved before the migration.
        legacy_agent = EnvAgentAi(openai_api_key="key", model="gpt-4o", temperature=0.2)
        self.assertEqual(legacy_agent.get_model(), "openai:gpt-4o")
