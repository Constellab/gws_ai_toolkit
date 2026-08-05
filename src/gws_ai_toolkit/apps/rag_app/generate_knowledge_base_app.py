from typing import cast

from gws_core import (
    AppConfig,
    AppType,
    BoolParam,
    ConfigParams,
    ConfigSpecs,
    File,
    InputSpec,
    InputSpecs,
    OutputSpec,
    OutputSpecs,
    ReflexResource,
    StrParam,
    Task,
    TaskInputs,
    TaskOutputs,
    app_decorator,
    task_decorator,
)


@app_decorator("RagAppAppConfig", app_type=AppType.REFLEX, human_name="Generate RagApp app")
class RagAppAppConfig(AppConfig):
    # retrieve the path of the app folder, relative to this file
    # the app code folder starts with a underscore to avoid being loaded when the brick is loaded
    def get_app_folder_path(self):
        return self.get_app_folder_from_relative_path(__file__, "_rag_app")


@task_decorator(
    "GenerateKnowledgeBaseApp",
    human_name="Generate Constellab Search",
    short_description="Generate the Constellab search app on the embedded knowledge-base stack",
    style=ReflexResource.copy_style(),
)
class GenerateKnowledgeBaseApp(Task):
    """
    Task that generates the Constellab Search app on the embedded knowledge-base stack
    (LlamaIndex + LanceDB): chat profiles bound to knowledge bases, and a knowledge-base manager to
    import and index documents.

    Configuration:
        - ``chat_app_name``: Name of the chat app. All conversations are associated to this chat name.
        - ``openai_credentials_name``: Optional name of an "other" credentials entry holding the
          OpenAI API key used for embedding and chat completion. Without one, the lab-wide
          ``OPENAI_API_KEY`` is used. A plain string rather than a ``CredentialsParam``, since the
          latter stringifies an absent value to the literal ``"None"`` before the task ever runs.
        - ``show_admin_history``: Whether to display the admin history page in the app, which allows
          browsing all conversations from all users.
        - ``requires_authentication``: Whether the app requires authentication. If not, every user is
          associated with the System user.
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
            "chat_app_name": StrParam(
                human_name="Chat app name",
                short_description="Name of the chat app. All conversations are associated to this chat name.",
            ),
            "openai_credentials_name": StrParam(
                human_name="OpenAI credentials name",
                short_description="Name of an 'other' credentials entry holding the OpenAI API key "
                "used for embedding and chat completion. Optional: without one, the lab-wide "
                "OPENAI_API_KEY is used.",
                optional=True,
            ),
            "show_admin_history": BoolParam(
                human_name="Show admin history",
                short_description="Show the admin history page to browse all conversations",
                default_value=False,
            ),
            "requires_authentication": BoolParam(
                human_name="Requires authentication",
                short_description="Whether the app requires authentication. If not every user will be associated with the System user.",
                default_value=True,
            ),
        }
    )

    def run(self, params: ConfigParams, inputs: TaskInputs) -> TaskOutputs:
        """Run the task"""

        reflex_resource = ReflexResource()

        reflex_resource = self.configure_reflex_resource(reflex_resource, params)

        app_config_file: File = cast(File, inputs["app_config"])
        reflex_resource = self.set_configuration_file_path(reflex_resource, app_config_file)

        reflex_resource.set_app_config(RagAppAppConfig())

        reflex_resource.set_requires_authentication(params["requires_authentication"])

        reflex_resource.set_enterprise_app(True)

        reflex_resource.name = "Search"

        return {"streamlit_app": reflex_resource}

    @classmethod
    def configure_reflex_resource(
        cls, reflex_resource: ReflexResource, params: ConfigParams
    ) -> ReflexResource:
        """Build a ReflexResource for the knowledge-base search app.

        Exposed as a classmethod so an app that embeds this one (e.g. ``GenerateFullApp``) can reuse
        the configuration logic instead of duplicating it.
        """
        reflex_resource.set_param("chat_app_name", params["chat_app_name"])

        openai_credentials_name: str | None = params.get("openai_credentials_name")
        if openai_credentials_name:
            reflex_resource.set_param(
                "knowledge_base_openai_credentials_name", openai_credentials_name
            )

        reflex_resource.set_param("show_admin_history", params["show_admin_history"])

        return reflex_resource

    @classmethod
    def set_configuration_file_path(
        cls, reflex_resource: ReflexResource, app_config_file: File
    ) -> ReflexResource:
        """Set the configuration file path in the reflex resource."""
        reflex_resource.add_resource(app_config_file, create_new_resource=False)
        reflex_resource.set_param("configuration_file_path", app_config_file.path)

        return reflex_resource
