import tempfile

from gws_ai_toolkit.apps.ai_table_standalone_app.generate_ai_table_standalone_app import (
    GenerateAiTableStandaloneApp,
)
from gws_ai_toolkit.apps.full_app.generate_full_app import GenerateFullApp
from gws_ai_toolkit.apps.rag_app.generate_rag_app import GenerateDatahubRagFlowApp
from gws_core import File
from gws_core.credentials.credentials import Credentials
from gws_core.credentials.credentials_type import CredentialsType
from gws_core.resource.resource_dto import ResourceOrigin
from gws_core.resource.resource_model import ResourceModel
from gws_core.test.app_tester import AppTester
from gws_core.test.base_test_case import BaseTestCase


# test_apps
class TestApps(BaseTestCase):
    _credentials_name: str | None = None

    @classmethod
    def init_before_test(cls):
        super().init_before_test()
        credentials = Credentials()
        credentials.name = "test_credentials"
        credentials.type = CredentialsType.OTHER
        credentials.data = {
            "data": [{"key": "route", "value": "fake_key"}, {"key": "api_key", "value": "fake_key"}]
        }
        credentials.save()
        cls._credentials_name = credentials.name

    def _create_empty_config_file(self) -> File:
        """Create a File resource containing an empty JSON object."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as tmp:
            tmp.write("{}")
            tmp_path = tmp.name
        return File(tmp_path)

    def test_rag_app(self):
        config_file = self._create_empty_config_file()

        AppTester.test_app_from_task(
            test_case=self,
            generate_task_type=GenerateDatahubRagFlowApp,
            app_output_name="streamlit_app",
            input_resources={"app_config": config_file},
            config_values={
                "chat_app_name": "test",
                "ragflow_credentials": self._credentials_name,
                "rag_dataset_id": "123",
                "rag_chat_id": "123",
                "resource_tag_key": "test_key",
                "resource_tag_value": "test_value",
            },
        )

    def test_full_app(self):
        config_file = self._create_empty_config_file()

        AppTester.test_app_from_task(
            test_case=self,
            generate_task_type=GenerateFullApp,
            app_output_name="streamlit_app",
            input_resources={"app_config": config_file},
            config_values={
                "chat_app_name": "test",
                "ragflow_credentials": self._credentials_name,
                "rag_dataset_id": "123",
                "rag_chat_id": "123",
                "resource_tag_key": "test_key",
                "resource_tag_value": "test_value",
            },
        )

    def test_ai_table_standalone_app(self):
        config_file = self._create_empty_config_file()

        AppTester.test_app_from_task(
            test_case=self,
            generate_task_type=GenerateAiTableStandaloneApp,
            app_output_name="reflex_app",
            input_resources={"app_config": config_file},
        )
