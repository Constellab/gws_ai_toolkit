from typing import cast

from gws_ai_toolkit.apps.rag_app.generate_rag_app import GenerateDatahubRagFlowApp
from gws_core import (
    AppConfig,
    AppType,
    ConfigParams,
    ConfigSpecs,
    File,
    InputSpec,
    InputSpecs,
    OutputSpec,
    OutputSpecs,
    ReflexResource,
    Task,
    TaskInputs,
    TaskOutputs,
    app_decorator,
    task_decorator,
)


@app_decorator("FullAppAppConfig", app_type=AppType.REFLEX, human_name="Generate FullApp app")
class FullAppAppConfig(AppConfig):
    # retrieve the path of the app folder, relative to this file
    # the app code folder starts with a underscore to avoid being loaded when the brick is loaded
    def get_app_folder_path(self):
        return self.get_app_folder_from_relative_path(__file__, "_full_app")


@task_decorator("GenerateFullApp", human_name="Generate FullApp app", style=ReflexResource.copy_style())
class GenerateFullApp(Task):
    """
    Task that generates the FullApp app.
    """

    input_specs = InputSpecs(
        {
            "app_config": InputSpec(
                File,
                human_name="App config file",
                short_description="The app config will be saved in this file. Can be empty to use the default config.",
            ),
        }
    )
    output_specs = OutputSpecs({"streamlit_app": OutputSpec(ReflexResource)})

    config_specs = ConfigSpecs(
        {
            **GenerateDatahubRagFlowApp.config_specs.specs,
        }
    )

    def run(self, params: ConfigParams, inputs: TaskInputs) -> TaskOutputs:
        """Run the task"""

        reflex_resource = ReflexResource()

        GenerateDatahubRagFlowApp.configure_reflex_resource(reflex_resource, params)

        # add the config file to the reflex resource and set the configuration file path
        app_config_file: File = cast(File, inputs["app_config"])
        reflex_resource = GenerateDatahubRagFlowApp.set_configuration_file_path(reflex_resource, app_config_file)

        reflex_resource.set_app_config(FullAppAppConfig())
        reflex_resource.name = "FullApp app"

        # TODO to remove
        # For the test, we disable the authentication
        reflex_resource.set_requires_authentication(False)

        reflex_resource.set_enterprise_app(True)

        return {"streamlit_app": reflex_resource}
