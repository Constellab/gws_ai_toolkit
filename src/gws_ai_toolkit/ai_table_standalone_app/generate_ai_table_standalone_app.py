from typing import cast

from gws_core import (AppConfig, AppType, ConfigParams, ConfigSpecs, File,
                      Folder, InputSpec, InputSpecs, OutputSpec, OutputSpecs,
                      ReflexResource, Task, TaskInputs, TaskOutputs,
                      app_decorator, task_decorator)


@app_decorator("AiTableStandaloneAppAppConfig", app_type=AppType.REFLEX,
               human_name="Generate AiTableStandaloneApp app")
class AiTableStandaloneAppAppConfig(AppConfig):

    # retrieve the path of the app folder, relative to this file
    # the app code folder starts with a underscore to avoid being loaded when the brick is loaded
    def get_app_folder_path(self):
        return self.get_app_folder_from_relative_path(__file__, "_ai_table_standalone_app")


@task_decorator("GenerateAiTableStandaloneApp", human_name="Generate AiTableStandaloneApp app",
                style=ReflexResource.copy_style())
class GenerateAiTableStandaloneApp(Task):
    """
    Task that generates the AiTableStandaloneApp app.
    """

    input_specs = InputSpecs({
        'app_config': InputSpec(File, human_name="App config file", short_description="The app config file to use"),
        'history_folder': InputSpec(Folder, human_name="History folder", short_description="The history folder to use")
    })
    output_specs = OutputSpecs({
        'reflex_app': OutputSpec(ReflexResource)
    })

    config_specs = ConfigSpecs({})

    def run(self, params: ConfigParams, inputs: TaskInputs) -> TaskOutputs:
        """ Run the task """

        reflex_app = ReflexResource()

        reflex_app.set_app_config(AiTableStandaloneAppAppConfig())
        reflex_app.name = "AiTableStandaloneApp"

        # add the config file to the reflex resource and set the configuration file path
        app_config_file: File = cast(File, inputs['app_config'])
        reflex_app.add_resource(app_config_file, create_new_resource=False)
        reflex_app.set_param('configuration_file_path', app_config_file.path)

        # add the history folder
        history_folder: Folder = cast(Folder, inputs['history_folder'])
        reflex_app.add_resource(history_folder, create_new_resource=False)
        reflex_app.set_param('history_folder_path', history_folder.path)

        reflex_app.set_enterprise_app(True)

        # TODO to remove
        # For the test, we disable the authentication
        reflex_app.set_requires_authentication(False)

        return {"reflex_app": reflex_app}
