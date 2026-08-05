from gws_ai_toolkit.apps.ai_table_standalone_app.generate_ai_table_standalone_app import (
    GenerateAiTableStandaloneApp,
)
from gws_core.test.app_tester import AppTester
from gws_core.test.base_test_case import BaseTestCase

from .apps_test_helper import create_empty_config_file


# test_ai_table_standalone_app
class TestAiTableStandaloneApp(BaseTestCase):
    def test_ai_table_standalone_app(self):
        config_file = create_empty_config_file()

        AppTester.test_app_compiles_from_task(
            test_case=self,
            generate_task_type=GenerateAiTableStandaloneApp,
            app_output_name="reflex_app",
            input_resources={"app_config": config_file},
        )
