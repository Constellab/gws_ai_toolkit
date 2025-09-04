from gws_core import (ConfigParams, AppConfig, AppType, OutputSpec,
                      OutputSpecs, ReflexResource, Task, TaskInputs,
                      TaskOutputs, app_decorator, task_decorator, 
                      InputSpecs, ConfigSpecs)


@app_decorator("MyNewAppAppConfig", app_type=AppType.REFLEX,
               human_name="Generate MyNewApp app")
class MyNewAppAppConfig(AppConfig):

    # retrieve the path of the app folder, relative to this file
    # the app code folder starts with a underscore to avoid being loaded when the brick is loaded
    def get_app_folder_path(self):
        return self.get_app_folder_from_relative_path(__file__, "_my_new_app")


@task_decorator("GenerateMyNewApp", human_name="Generate MyNewApp app",
                style=ReflexResource.copy_style())
class GenerateMyNewApp(Task):
    """
    Task that generates the MyNewApp app.
    """

    input_specs = InputSpecs()
    output_specs = OutputSpecs({
        'reflex_app': OutputSpec(ReflexResource)
    })

    config_specs = ConfigSpecs({})

    def run(self, params: ConfigParams, inputs: TaskInputs) -> TaskOutputs:
        """ Run the task """

        reflex_app = ReflexResource()

        reflex_app.set_app_config(MyNewAppAppConfig())
        reflex_app.name = "MyNewApp"

        return {"reflex_app": reflex_app}
