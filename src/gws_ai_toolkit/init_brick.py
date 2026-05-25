import os

from gws_core import (
    AuthenticateUser,
    Event,
    EventListener,
    File,
    FileHelper,
    Logger,
    ResourceModel,
    ResourceOrigin,
    ResourceSearchBuilder,
    ScenarioCreationType,
    ScenarioProxy,
    Settings,
    Tag,
    event_listener,
)

from .apps.ai_table_standalone_app.analytics_app_constants import (
    ANALYTICS_APP_TAG_KEY,
    ANALYTICS_APP_TAG_VALUE,
)
from .apps.ai_table_standalone_app.generate_ai_table_standalone_app import (
    GenerateAiTableStandaloneApp,
)


@event_listener
class GwsAiToolkitListener(EventListener):
    """Listener that creates the Constellab Analytics app on lab startup.

    If no analytics app exists yet (no resource carrying the analytics tag), a
    scenario running :class:`GenerateAiTableStandaloneApp` is queued to generate
    one.
    """

    def handle(self, event: Event) -> None:
        if event.type == "system" and event.action == "started":
            self._create_analytics_app_if_none_exists()

    def _create_analytics_app_if_none_exists(self) -> None:
        """Generate the analytics app scenario if no analytics app exists yet."""
        try:
            if self._analytics_app_exists():
                return

            with AuthenticateUser.system_user():
                # the task needs a config file as input: create an empty json
                # file resource, marked as uploaded
                app_config_resource = self._create_empty_json_resource()

                # build a scenario running GenerateAiTableStandaloneApp with
                # the config file connected to its 'app_config' input
                scenario = ScenarioProxy(
                    title="Generate Constellab Analytics app",
                    creation_type=ScenarioCreationType.AUTO,
                )
                protocol = scenario.get_protocol()
                generate_task = protocol.add_task(GenerateAiTableStandaloneApp)
                protocol.add_resource(
                    "app_config_file",
                    app_config_resource.id,
                    generate_task << "app_config",
                )
                protocol.add_output(
                    "reflex_app_output", generate_task >> "reflex_app"
                )

                scenario.add_to_queue()
        except Exception as err:
            Logger.error(
                f"Error while creating the Constellab Analytics app. Error: {err}"
            )

    def _analytics_app_exists(self) -> bool:
        """Return True if an analytics app resource already exists in the lab."""
        search_builder = ResourceSearchBuilder()
        search_builder.add_tag_filter(
            Tag(ANALYTICS_APP_TAG_KEY, ANALYTICS_APP_TAG_VALUE)
        )
        return search_builder.search_first() is not None

    def _create_empty_json_resource(self) -> ResourceModel:
        """Create an empty json File resource marked as uploaded."""
        temp_dir = Settings.make_temp_dir()
        file_path = os.path.join(temp_dir, "analytics_app_config.json")
        FileHelper.create_empty_file_if_not_exist(file_path)

        # write an empty json object so the file is valid json
        json_file = File(file_path)
        json_file.write("{}", mode="w+t")

        return ResourceModel.save_from_resource(
            json_file, origin=ResourceOrigin.UPLOADED
        )
