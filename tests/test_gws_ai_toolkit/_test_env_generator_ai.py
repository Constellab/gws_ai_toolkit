"""
Test file for env_generator_ai tasks: CondaEnvGeneratorAi and PipEnvGeneratorAi
"""

import os
from unittest import TestCase

from gws_ai_toolkit.core.agents.env_generator_ai import CondaEnvGeneratorAi, PipEnvGeneratorAi
from gws_core import TaskRunner


# test_env_generator_ai.py
class TestEnvGeneratorAi(TestCase):
    """Test cases for environment generator AI tasks"""

    def test_conda_env_generator(self):
        """Test the CondaEnvGeneratorAi task with a simple package requirement"""
        # Skip test if OPENAI_API_KEY is not set
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            self.skipTest("OPENAI_API_KEY environment variable is not set")

        # Configure the task with simple requirements
        runner = TaskRunner(
            task_type=CondaEnvGeneratorAi,
            params={
                "env_type": "conda",
                "user_prompt": "I need numpy version 1.24 and pandas for data analysis",
                "existing_env_file": None,
            },
            inputs={},
        )

        # Run the task
        outputs = runner.run()

        # Validate outputs
        env_file = outputs["env_file"]
        self.assertIsNotNone(env_file, "Environment file should be generated")

        # Read the generated file content
        content = env_file.read()
        self.assertIsNotNone(content, "File content should not be None")
        self.assertGreater(len(content), 0, "File content should not be empty")

        # Validate that it's a valid YAML-like structure with expected keywords
        self.assertIn("dependencies", content.lower(), "Should contain 'dependencies' keyword")

        # Check for expected packages
        content_lower = content.lower()
        self.assertTrue(
            "numpy" in content_lower or "pandas" in content_lower,
            "Should contain at least one of the requested packages",
        )

    def test_conda_env_generator_fix_existing(self):
        """Test the CondaEnvGeneratorAi task fixing an existing problematic environment file"""
        # Skip test if OPENAI_API_KEY is not set
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            self.skipTest("OPENAI_API_KEY environment variable is not set")

        # Provide a problematic existing environment file with incompatible versions
        existing_env = """
name: myenv
channels:
  - defaults
dependencies:
  - python=3.11
  - numpy=1.19.0
  - pandas=2.0.0
  - scipy=1.8.0
"""

        # Configure the task to fix the existing environment
        runner = TaskRunner(
            task_type=CondaEnvGeneratorAi,
            params={
                "env_type": "conda",
                "user_prompt": "Fix this environment file",
                "existing_env_file": existing_env,
            },
            inputs={},
        )

        # Run the task
        outputs = runner.run()

        # Validate outputs
        env_file = outputs["env_file"]
        self.assertIsNotNone(env_file, "Environment file should be generated")

        # Read the generated file content
        content = env_file.read()
        self.assertIsNotNone(content, "File content should not be None")
        self.assertGreater(len(content), 0, "File content should not be empty")

        # Validate that it's a valid YAML-like structure
        self.assertIn("dependencies", content.lower(), "Should contain 'dependencies' keyword")

        # Check that packages are still present
        content_lower = content.lower()
        self.assertIn("numpy", content_lower, "Should contain numpy package")
        self.assertIn("pandas", content_lower, "Should contain pandas package")

    def test_pipenv_generator(self):
        """Test the PipEnvGeneratorAi task with a simple package requirement"""
        # Skip test if OPENAI_API_KEY is not set
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            self.skipTest("OPENAI_API_KEY environment variable is not set")

        # Configure the task with simple requirements
        runner = TaskRunner(
            task_type=PipEnvGeneratorAi,
            params={
                "user_prompt": "I need requests version 2.31.0 for making HTTP API calls, pytest version 7.4.0 for unit testing, and pytest-cov for test coverage reports",
                "existing_pipfile": None,
            },
            inputs={},
        )

        # Run the task
        outputs = runner.run()

        # Validate outputs
        pipfile = outputs["env_file"]
        self.assertIsNotNone(pipfile, "Pipfile should be generated")

        # Read the generated file content
        content = pipfile.read()
        self.assertIsNotNone(content, "File content should not be None")
        self.assertGreater(len(content), 0, "File content should not be empty")

        # Validate that it's a valid Pipfile-like structure with expected sections
        content_lower = content.lower()
        self.assertIn("packages", content_lower, "Should contain '[packages]' section")

        # Check for expected packages
        self.assertTrue(
            "requests" in content_lower or "pytest" in content_lower,
            "Should contain at least one of the requested packages",
        )
