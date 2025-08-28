from gws_ai_toolkit.rag.common.rag_enums import RagResourceSyncMode
from gws_core import (AppConfig, AppType, BoolParam, ConfigParams, ConfigSpecs,
                      CredentialsDataOther, CredentialsParam, InputSpecs,
                      IntParam, OutputSpec, OutputSpecs, ReflexResource,
                      StrParam, Task, TaskInputs, TaskOutputs, app_decorator,
                      task_decorator)
from gws_core.core.utils.utils import Utils


@app_decorator("RagAppAppConfig", app_type=AppType.REFLEX,
               human_name="Generate RagApp app")
class RagAppAppConfig(AppConfig):

    # retrieve the path of the app folder, relative to this file
    # the app code folder starts with a underscore to avoid being loaded when the brick is loaded
    def get_app_folder_path(self):
        return self.get_app_folder_from_relative_path(__file__, "_rag_app")


@task_decorator("GenerateDatahubRagDifyApp", human_name="Generate Datahub Dify app",
                style=ReflexResource.copy_style())
class GenerateDatahubRagDifyApp(Task):
    """
    Generate the Datahub RAG app using Dify rag.

    Configuration :
    - Resource sync mode: The mode for the resource to sync with the RAG platform (datahub or tag)
        - if 'datahub' is selected, the app will sync resources store in the datahub from the space
        - if 'tag' is selected, the app will sync resources with the tag 'send_to_rag:true'
    """

    input_specs = InputSpecs()
    output_specs = OutputSpecs({
        'streamlit_app': OutputSpec(ReflexResource)
    })

    config_specs = ConfigSpecs({
        'chat_credentials': CredentialsParam(
            human_name="Chat credentials",
            short_description="Credentials to access the RAG platform chat",
        ),
        'dataset_credentials': CredentialsParam(
            human_name="Knowledge Base credentials",
            short_description="Credentials to access RAG platform knowledge bases",
        ),
        'dataset_id': StrParam(
            human_name="Knowledge Base ID",
            short_description="ID of the knowledge base to use",
        ),
        'resource_sync_mode': StrParam(
            human_name="Resource sync mode",
            short_description="Mode for the resource to sync with the RAG platform. More info in documentation.",
            allowed_values=Utils.get_literal_values(RagResourceSyncMode),
            default_value='datahub'
        ),
        'show_config_page': BoolParam(
            human_name="Show config page",
            short_description="Show the config page",
            default_value=True
        )
    })

    def run(self, params: ConfigParams, inputs: TaskInputs) -> TaskOutputs:
        """ Run the task """

        reflex_resource = ReflexResource()

        chat_credentials_data: CredentialsDataOther = params['chat_credentials']
        reflex_resource.set_param('chat_credentials_name', chat_credentials_data.meta.name)

        dataset_credentials_data: CredentialsDataOther = params['dataset_credentials']
        reflex_resource.set_param('dataset_credentials_name', dataset_credentials_data.meta.name)

        reflex_resource.set_param('dataset_id', params['dataset_id'])
        reflex_resource.set_param('resource_sync_mode', params['resource_sync_mode'])
        reflex_resource.set_param('show_config_page', params['show_config_page'])
        reflex_resource.set_param('rag_provider', 'dify')
        reflex_resource.set_param('chat_id', None)

        reflex_resource.set_app_config(RagAppAppConfig())
        reflex_resource.name = "DataHub RAG app"

        return {"streamlit_app": reflex_resource}


@task_decorator("GenerateDatahubRagFlowApp2", human_name="Generate Datahub Ragflow app",
                style=ReflexResource.copy_style())
class GenerateDatahubRagFlowApp2(Task):
    """
    Task that generates the DatahubRagApp app.
    """

    input_specs = InputSpecs()
    output_specs = OutputSpecs({
        'streamlit_app': OutputSpec(ReflexResource)
    })

    config_specs = ConfigSpecs({
        'ragflow_credentials': CredentialsParam(
            human_name="RAGFlow credentials",
            short_description="Credentials to access RAGFlow",
        ),
        'dataset_id': StrParam(
            human_name="Dataset ID",
            short_description="ID of the dataset to use",
        ),
        'show_config_page': BoolParam(
            human_name="Show config page",
            short_description="Show the config page",
            default_value=True
        ),
        'chat_id': StrParam(
            human_name="Chat ID",
            short_description="ID of the chat to use",
        )
    })

    def run(self, params: ConfigParams, inputs: TaskInputs) -> TaskOutputs:
        """ Run the task """

        resource_resource = ReflexResource()

        # set both credentials using the ragflow_credentials
        ragflow_credentials_data: CredentialsDataOther = params['ragflow_credentials']
        resource_resource.set_param('chat_credentials_name', ragflow_credentials_data.meta.name)
        resource_resource.set_param('dataset_credentials_name', ragflow_credentials_data.meta.name)

        # For Ragflow, only the Tag resource mode is supported
        resource_sync_mode: RagResourceSyncMode = 'tag'
        resource_resource.set_param('resource_sync_mode', resource_sync_mode)
        resource_resource.set_param('dataset_id', params['dataset_id'])
        resource_resource.set_param('show_config_page', params['show_config_page'])
        resource_resource.set_param('chat_id', params['chat_id'])
        resource_resource.set_param('rag_provider', 'ragflow')

        resource_resource.set_app_config(RagAppAppConfig())
        resource_resource.name = "DataHub RAG app"

        return {"streamlit_app": resource_resource}
