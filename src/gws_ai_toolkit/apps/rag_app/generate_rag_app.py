from typing import cast

from gws_ai_toolkit.rag.common.rag_enums import RagResourceSyncMode
from gws_core import (
    AppConfig,
    AppType,
    BoolParam,
    ConfigParams,
    ConfigSpecs,
    CredentialsDataOther,
    CredentialsParam,
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
    Utils,
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
    "GenerateDatahubRagDifyApp",
    human_name="Generate Constellab search Dify",
    short_description="Generate the Constellab search app using Dify RAG",
    style=ReflexResource.copy_style(),
)
class GenerateDatahubRagDifyApp(Task):
    """
    Task that generates the Constellab Search app using Dify as the RAG engine.

    This task creates a Reflex-based search application that indexes and queries resources through a
    Dify-powered RAG pipeline. It requires separate credentials for the chat and knowledge base APIs.

    Configuration:
        - ``chat_app_name``: Name of the chat app. All conversations are associated to this chat name.
        - ``chat_credentials``: Credentials to access the Dify chat API.
        - ``dataset_credentials``: Credentials to access the Dify knowledge base API.
        - ``dataset_id``: ID of the Dify knowledge base to use.
        - ``resource_sync_mode``: Determines which resources are synced with the RAG platform.
            - ``"datahub"``: syncs resources stored in the datahub from the space.
            - ``"tag"``: syncs only resources matching the tag defined by ``resource_tag_key`` / ``resource_tag_value``.
        - ``resource_tag_key``: Tag key used to filter resources for sync (only used when ``resource_sync_mode``
          is ``"tag"``).
        - ``resource_tag_value``: Tag value that must be paired with ``resource_tag_key`` for a resource to be
          synced (only used when ``resource_sync_mode`` is ``"tag"``).
        - ``show_config_page``: Whether to display the configuration page in the app.
    """

    input_specs = InputSpecs(
        {
            "app_config": InputSpec(
                File, human_name="App config file", short_description="The app config file to use"
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
            "chat_credentials": CredentialsParam(
                human_name="Chat credentials",
                short_description="Credentials to access the RAG platform chat",
            ),
            "dataset_credentials": CredentialsParam(
                human_name="Knowledge Base credentials",
                short_description="Credentials to access RAG platform knowledge bases",
            ),
            "dataset_id": StrParam(
                human_name="Knowledge Base ID",
                short_description="ID of the knowledge base to use",
            ),
            "resource_sync_mode": StrParam(
                human_name="Resource sync mode",
                short_description="Mode for the resource to sync with the RAG platform. More info in documentation.",
                allowed_values=Utils.get_literal_values(RagResourceSyncMode),
                default_value="datahub",
            ),
            "resource_tag_key": StrParam(
                human_name="Resource tag key",
                short_description="Tag key for resources to sync (only used when resource_sync_mode is 'tag')",
                optional=True,
            ),
            "resource_tag_value": StrParam(
                human_name="Resource tag value",
                short_description="Tag value for resources to sync (only used when resource_sync_mode is 'tag')",
                optional=True,
            ),
            "show_config_page": BoolParam(
                human_name="Show config page",
                short_description="Show the config page",
                default_value=True,
            ),
        }
    )

    def run(self, params: ConfigParams, inputs: TaskInputs) -> TaskOutputs:
        """Run the task"""

        reflex_resource = ReflexResource()

        # set the chat app name
        reflex_resource.set_param("chat_app_name", params.get("chat_app_name"))

        chat_credentials_data: CredentialsDataOther = params["chat_credentials"]
        reflex_resource.set_param("rag_chat_credentials_name", chat_credentials_data.meta.name)

        dataset_credentials_data: CredentialsDataOther = params["dataset_credentials"]
        reflex_resource.set_param(
            "rag_dataset_credentials_name", dataset_credentials_data.meta.name
        )

        reflex_resource.set_param("rag_dataset_id", params["rag_dataset_id"])
        reflex_resource.set_param("resource_sync_mode", params["resource_sync_mode"])
        reflex_resource.set_param("show_config_page", params["show_config_page"])
        reflex_resource.set_param("rag_provider", "dify")
        reflex_resource.set_param("rag_chat_id", None)

        if params.get("resource_tag_key"):
            reflex_resource.set_param("resource_tag_key", params["resource_tag_key"])
        if params.get("resource_tag_value"):
            reflex_resource.set_param("resource_tag_value", params["resource_tag_value"])

        # add the config file to the reflex resource and set the configuration file path
        app_config_file: File = cast(File, inputs["app_config"])
        reflex_resource.add_resource(app_config_file, create_new_resource=False)
        reflex_resource.set_param("configuration_file_path", app_config_file.path)

        reflex_resource.set_app_config(RagAppAppConfig())
        reflex_resource.name = "Search"

        # TODO to remove
        # For the test, we disable the authentication
        reflex_resource.set_requires_authentication(False)

        reflex_resource.set_enterprise_app(True)

        reflex_resource.name = "Constellab Search"

        return {"streamlit_app": reflex_resource}


@task_decorator(
    "GenerateDatahubRagFlowApp",
    human_name="Generate Constellab Search Ragflow",
    short_description="Generate the Constellab search app using Ragflow RAG",
    style=ReflexResource.copy_style(),
)
class GenerateDatahubRagFlowApp(Task):
    """
    Task that generates the Constellab Search app using RAGFlow as the RAG engine.

    This task creates a Reflex-based search application that indexes and queries resources through a
    RAGFlow-powered RAG pipeline. Unlike the Dify variant, RAGFlow only supports the ``"tag"`` resource
    sync mode, and uses a single set of credentials for both chat and knowledge base access.

    This class also exposes ``configure_reflex_resource`` and ``set_configuration_file_path`` as class
    methods so that subclasses (e.g. ``GenerateFullApp``) can reuse the configuration logic.

    Configuration:
        - ``chat_app_name``: Name of the chat app. All conversations are associated to this chat name.
        - ``ragflow_credentials``: Credentials to access RAGFlow (used for both chat and dataset APIs).
        - ``rag_dataset_id``: ID of the RAGFlow dataset (knowledge base) to use.
        - ``rag_chat_id``: ID of the RAGFlow chat assistant to use.
        - ``resource_tag_key``: Tag key used to filter which resources are synced with the RAG platform.
          Only resources carrying a tag with this key (and matching value) will be indexed.
        - ``resource_tag_value``: Tag value that must be paired with ``resource_tag_key`` for a resource
          to be synced with the RAG platform.
        - ``show_config_page``: Whether to display the configuration page in the app.
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
            "ragflow_credentials": CredentialsParam(
                human_name="RAGFlow credentials",
                short_description="Credentials to access RAGFlow",
            ),
            "rag_dataset_id": StrParam(
                human_name="Ragflow dataset ID",
                short_description="ID of the Ragflow dataset to use",
            ),
            "rag_chat_id": StrParam(
                human_name="Ragflow chat ID",
                short_description="ID of the Ragflow chat to use",
            ),
            "resource_tag_key": StrParam(
                human_name="Resource tag key",
                short_description="Tag key for resources to sync",
            ),
            "resource_tag_value": StrParam(
                human_name="Resource tag value",
                short_description="Tag value for resources to sync",
            ),
            "show_config_page": BoolParam(
                human_name="Show config page",
                short_description="Show the config page",
                default_value=True,
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

        # configure the reflex resource using the class method
        reflex_resource = self.configure_reflex_resource(reflex_resource, params)

        # add the config file to the reflex resource and set the configuration file path
        app_config_file: File = cast(File, inputs["app_config"])
        reflex_resource = self.set_configuration_file_path(reflex_resource, app_config_file)

        reflex_resource.set_app_config(RagAppAppConfig())
        reflex_resource.name = "DataHub RAG app"

        # Set the authentication requirement based on the config parameter
        reflex_resource.set_requires_authentication(params["requires_authentication"])

        reflex_resource.name = "Search"

        return {"streamlit_app": reflex_resource}

    @classmethod
    def configure_reflex_resource(
        cls, reflex_resource: ReflexResource, params: ConfigParams
    ) -> ReflexResource:
        """Build a ReflexResource for the Datahub RAGFlow app."""

        reflex_resource.set_param("chat_app_name", params["chat_app_name"])
        # set both credentials using the ragflow_credentials
        ragflow_credentials_data: CredentialsDataOther = params["ragflow_credentials"]
        reflex_resource.set_param("rag_chat_credentials_name", ragflow_credentials_data.meta.name)
        reflex_resource.set_param(
            "rag_dataset_credentials_name", ragflow_credentials_data.meta.name
        )

        # For Ragflow, only the Tag resource mode is supported
        resource_sync_mode: RagResourceSyncMode = "tag"
        reflex_resource.set_param("resource_sync_mode", resource_sync_mode)
        reflex_resource.set_param("rag_dataset_id", params["rag_dataset_id"])
        reflex_resource.set_param("show_config_page", params["show_config_page"])
        reflex_resource.set_param("rag_chat_id", params["rag_chat_id"])
        reflex_resource.set_param("rag_provider", "ragflow")

        if params.get("resource_tag_key"):
            reflex_resource.set_param("resource_tag_key", params["resource_tag_key"])
        if params.get("resource_tag_value"):
            reflex_resource.set_param("resource_tag_value", params["resource_tag_value"])

        return reflex_resource

    @classmethod
    def set_configuration_file_path(
        cls, reflex_resource: ReflexResource, app_config_file: File
    ) -> ReflexResource:
        """Set the configuration file path in the reflex resource."""
        reflex_resource.add_resource(app_config_file, create_new_resource=False)
        reflex_resource.set_param("configuration_file_path", app_config_file.path)

        return reflex_resource
