
from gws_core.apps.app_config import AppConfig, app_decorator
from gws_core.apps.app_dto import AppType
from gws_core.config.config_params import ConfigParams
from gws_core.config.config_specs import ConfigSpecs
from gws_core.config.param.param_spec import BoolParam, IntParam, StrParam
from gws_core.credentials.credentials_param import CredentialsParam
from gws_core.credentials.credentials_type import CredentialsDataOther
from gws_core.io.io_spec import OutputSpec
from gws_core.io.io_specs import InputSpecs, OutputSpecs
from gws_core.streamlit.streamlit_resource import StreamlitResource
from gws_core.task.task import Task
from gws_core.task.task_decorator import task_decorator
from gws_core.task.task_io import TaskInputs, TaskOutputs


@app_decorator("DatahubRagApp", app_type=AppType.STREAMLIT,
               human_name="Generate DataHub RAG app")
class DatahubRagAppDashboard(AppConfig):

    # retrieve the path of the app folder, relative to this file
    # the dashboard code folder starts with a underscore to avoid being loaded when the brick is loaded
    def get_app_folder_path(self):
        return self.get_app_folder_from_relative_path(__file__, "_datahub_dify_app")


@task_decorator("GenerateDatahubRagDifyApp", human_name="Generate Datahub Dify app",
                style=StreamlitResource.copy_style())
class GenerateDatahubRagDifyApp(Task):
    """
    Task that generates the DatahubRagApp app.
    """

    input_specs = InputSpecs()
    output_specs = OutputSpecs({
        'streamlit_app': OutputSpec(StreamlitResource)
    })

    config_specs = ConfigSpecs({
        'chat_credentials': CredentialsParam(
            human_name="Chat credentials",
            short_description="Credentials to access the RAG platform chat",
        ),
        'knowledge_base_credentials': CredentialsParam(
            human_name="Knowledge Base credentials",
            short_description="Credentials to access RAG platform knowledge bases",
        ),
        'knowledge_base_id': StrParam(
            human_name="Knowledge Base ID",
            short_description="ID of the knowledge base to use",
        ),
        'show_config_page': BoolParam(
            human_name="Show config page",
            short_description="Show the config page",
            default_value=True
        ),
        'filter_rag_with_user_folders': BoolParam(
            human_name="Filter RAG with user folders",
            short_description="Filter RAG resources with user folders (only available with Dify)",
            default_value=True
        ),
        'root_folder_limit': IntParam(
            human_name="Root folder limit",
            short_description="Maximum number of root folders accessible by the user supported by the app",
            default_value=20
        ),
    })

    def run(self, params: ConfigParams, inputs: TaskInputs) -> TaskOutputs:
        """ Run the task """

        streamlit_app = StreamlitResource()

        chat_credentials_data: CredentialsDataOther = params['chat_credentials']
        streamlit_app.set_param('chat_credentials_name', chat_credentials_data.meta.name)

        knowledge_base_credentials_data: CredentialsDataOther = params['knowledge_base_credentials']
        streamlit_app.set_param('knowledge_base_credentials_name', knowledge_base_credentials_data.meta.name)

        streamlit_app.set_param('knowledge_base_id', params['knowledge_base_id'])
        streamlit_app.set_param('show_config_page', params['show_config_page'])
        streamlit_app.set_param('filter_rag_with_user_folders', params['filter_rag_with_user_folders'])
        streamlit_app.set_param('root_folder_limit', params['root_folder_limit'])
        streamlit_app.set_param('rag_provider', 'dify')
        streamlit_app.set_param('chat_id', None)

        streamlit_app.set_app_config(DatahubRagAppDashboard())
        streamlit_app.name = "DataHub RAG app"

        return {"streamlit_app": streamlit_app}


@task_decorator("GenerateDatahubRagFlowApp", human_name="Generate Datahub Ragflow app",
                style=StreamlitResource.copy_style())
class GenerateDatahubRagFlowApp(Task):
    """
    Task that generates the DatahubRagApp app.
    """

    input_specs = InputSpecs()
    output_specs = OutputSpecs({
        'streamlit_app': OutputSpec(StreamlitResource)
    })

    config_specs = ConfigSpecs({
        'ragflow_credentials': CredentialsParam(
            human_name="RAGFlow credentials",
            short_description="Credentials to access RAGFlow",
        ),
        'knowledge_base_id': StrParam(
            human_name="Knowledge Base ID",
            short_description="ID of the knowledge base to use",
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

        streamlit_app = StreamlitResource()

        # set both credentials using the ragflow_credentials
        ragflow_credentials_data: CredentialsDataOther = params['ragflow_credentials']
        streamlit_app.set_param('chat_credentials_name', ragflow_credentials_data.meta.name)
        streamlit_app.set_param('knowledge_base_credentials_name', ragflow_credentials_data.meta.name)

        streamlit_app.set_param('knowledge_base_id', params['knowledge_base_id'])
        streamlit_app.set_param('show_config_page', params['show_config_page'])
        streamlit_app.set_param('chat_id', params['chat_id'])

        # disable folder filter
        streamlit_app.set_param('filter_rag_with_user_folders', False)
        streamlit_app.set_param('root_folder_limit', 0)
        streamlit_app.set_param('rag_provider', 'ragflow')

        streamlit_app.set_app_config(DatahubRagAppDashboard())
        streamlit_app.name = "DataHub RAG app"

        return {"streamlit_app": streamlit_app}
