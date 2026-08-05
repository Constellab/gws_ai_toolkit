import tempfile

from gws_ai_toolkit.apps.ai_table_standalone_app.generate_ai_table_standalone_app import (
    GenerateAiTableStandaloneApp,
)
from gws_ai_toolkit.apps.full_app.generate_full_app import GenerateFullApp
from gws_ai_toolkit.apps.rag_app.generate_knowledge_base_app import GenerateKnowledgeBaseApp
from gws_core import File
from gws_core.test.app_tester import AppTester
from gws_core.test.base_test_case import BaseTestCase


# test_apps
class TestApps(BaseTestCase):
    def _create_empty_config_file(self) -> File:
        """Create a File resource containing an empty JSON object."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as tmp:
            tmp.write("{}")
            tmp_path = tmp.name
        return File(tmp_path)

    def test_rag_app(self):
        config_file = self._create_empty_config_file()

        AppTester.test_app_compiles_from_task(
            test_case=self,
            generate_task_type=GenerateKnowledgeBaseApp,
            app_output_name="streamlit_app",
            input_resources={"app_config": config_file},
            config_values={
                "chat_app_name": "test",
            },
        )

    def test_full_app(self):
        config_file = self._create_empty_config_file()

        AppTester.test_app_compiles_from_task(
            test_case=self,
            generate_task_type=GenerateFullApp,
            app_output_name="streamlit_app",
            input_resources={"app_config": config_file},
            config_values={
                "chat_app_name": "test",
            },
        )

    def test_ai_table_standalone_app(self):
        config_file = self._create_empty_config_file()

        AppTester.test_app_compiles_from_task(
            test_case=self,
            generate_task_type=GenerateAiTableStandaloneApp,
            app_output_name="reflex_app",
            input_resources={"app_config": config_file},
        )
