from gws_ai_toolkit.apps.full_app.generate_full_app import GenerateFullApp
from gws_core.test.app_tester import AppTester
from gws_core.test.base_test_case import BaseTestCase

from .apps_test_helper import create_empty_config_file


# test_full_app
class TestFullApp(BaseTestCase):
    def test_full_app(self):
        config_file = create_empty_config_file()

        AppTester.test_app_compiles_from_task(
            test_case=self,
            generate_task_type=GenerateFullApp,
            app_output_name="streamlit_app",
            input_resources={"app_config": config_file},
            config_values={
                "chat_app_name": "test",
            },
        )
