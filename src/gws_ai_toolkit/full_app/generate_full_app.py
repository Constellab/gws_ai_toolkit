from typing import cast

from gws_core import (AppConfig, AppType, BoolParam, ConfigParams, ConfigSpecs,
                      CredentialsDataOther, CredentialsParam, File, Folder,
                      InputSpec, InputSpecs, OutputSpec, OutputSpecs,
                      ReflexResource, StrParam, Task, TaskInputs, TaskOutputs,
                      app_decorator, task_decorator)

from gws_ai_toolkit.rag.common.rag_enums import RagResourceSyncMode


@app_decorator("FullAppAppConfig", app_type=AppType.REFLEX,
               human_name="Generate FullApp app")
class FullAppAppConfig(AppConfig):

    # retrieve the path of the app folder, relative to this file
    # the app code folder starts with a underscore to avoid being loaded when the brick is loaded
    def get_app_folder_path(self):
        return self.get_app_folder_from_relative_path(__file__, "_full_app")


@task_decorator("GenerateFullApp", human_name="Generate FullApp app",
                style=ReflexResource.copy_style())
class GenerateFullApp(Task):
    """
    Task that generates the FullApp app.
    """

    input_specs = InputSpecs({
        'app_config': InputSpec(File, human_name="App config file",
                                short_description="The app config will be saved in this file. Can be empty to use the default config."),
        'history_folder': InputSpec(Folder, human_name="History folder", short_description="The history folder to use")

    })
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
        'resource_tag_key': StrParam(
            human_name="Resource tag key",
            short_description="Tag key for resources to sync",
            optional=True
        ),
        'resource_tag_value': StrParam(
            human_name="Resource tag value",
            short_description="Tag value for resources to sync",
            optional=True
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

        reflex_resource = ReflexResource()

        # set both credentials using the ragflow_credentials
        ragflow_credentials_data: CredentialsDataOther = params['ragflow_credentials']
        reflex_resource.set_param('chat_credentials_name', ragflow_credentials_data.meta.name)
        reflex_resource.set_param('dataset_credentials_name', ragflow_credentials_data.meta.name)

        # For Ragflow, only the Tag resource mode is supported
        resource_sync_mode: RagResourceSyncMode = 'tag'
        reflex_resource.set_param('resource_sync_mode', resource_sync_mode)
        reflex_resource.set_param('dataset_id', params['dataset_id'])
        reflex_resource.set_param('show_config_page', params['show_config_page'])
        reflex_resource.set_param('chat_id', params['chat_id'])
        reflex_resource.set_param('rag_provider', 'ragflow')

        if params.get('resource_tag_key'):
            reflex_resource.set_param('resource_tag_key', params['resource_tag_key'])
        if params.get('resource_tag_value'):
            reflex_resource.set_param('resource_tag_value', params['resource_tag_value'])

        # add the config file to the reflex resource and set the configuration file path
        app_config_file: File = cast(File, inputs['app_config'])
        reflex_resource.add_resource(app_config_file, create_new_resource=False)
        reflex_resource.set_param('configuration_file_path', app_config_file.path)

        # Add the history folder to the reflex resource and set the history folder path
        history_folder: Folder = cast(Folder, inputs['history_folder'])
        reflex_resource.add_resource(history_folder, create_new_resource=False)
        reflex_resource.set_param('history_folder_path', history_folder.path)

        reflex_resource.set_app_config(FullAppAppConfig())
        reflex_resource.name = "FullApp app"

        # TODO to remove
        # For the test, we disable the authentication
        reflex_resource.set_requires_authentication(False)

        reflex_resource.set_enterprise_app(True)

        return {"streamlit_app": reflex_resource}
