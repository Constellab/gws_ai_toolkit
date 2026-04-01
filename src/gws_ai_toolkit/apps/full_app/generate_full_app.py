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


@task_decorator(
    "GenerateFullApp",
    human_name="Generate Constellab search with Analytics",
    short_description="Generate the Constellab Search app using Ragflow with the Analytics plugin",
    style=ReflexResource.copy_style(),
)
class GenerateFullApp(Task):
    """
    Task that generates the Constellab Search app with the Analytics plugin, using RAGFlow as the RAG engine.

    This app extends the base search app by allowing table resources (Excel, CSV, TSV, etc.) to be associated
    with the file resources sent to the RAG knowledge base. Associated resources are linked through a shared
    tag with the key ``"study"``: resources that share the same ``study`` tag value are considered part of the
    same study and will appear as associated resources in the app interface.

    Configuration (inherited from ``GenerateDatahubRagFlowApp``):
        - ``resource_tag_key``: The tag key used to select which resources are synced with the RAG platform.
          Only resources carrying a tag with this key (and matching value) will be indexed.
        - ``resource_tag_value``: The tag value that must be paired with ``resource_tag_key`` for a resource
          to be synced with the RAG platform.
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
        reflex_resource = GenerateDatahubRagFlowApp.set_configuration_file_path(
            reflex_resource, app_config_file
        )

        reflex_resource.set_app_config(FullAppAppConfig())

        reflex_resource.set_requires_authentication(params["requires_authentication"])

        reflex_resource.set_enterprise_app(True)

        reflex_resource.name = "Search"

        return {"streamlit_app": reflex_resource}
