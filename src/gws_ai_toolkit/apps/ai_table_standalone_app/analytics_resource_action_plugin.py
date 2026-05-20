from gws_core import (
    EntityAction,
    EntityActionPlugin,
    EntityActionResultDTO,
    EntityActionType,
    File,
    FileHelper,
    FrontService,
    ResourceModel,
    ResourceSearchBuilder,
    Table,
    Tag,
    Utils,
    entity_action_plugin,
)

from .analytics_app_constants import (
    ANALYTICS_APP_RESOURCE_QUERY_PARAM_KEY,
    ANALYTICS_APP_TAG_KEY,
    ANALYTICS_APP_TAG_VALUE,
)


@entity_action_plugin("analytics")
class AnalyticsResourceActionPlugin(EntityActionPlugin):
    """Adds an 'Open in Analytics' action to Table / CSV-file resources.

    Registered automatically when the gws_ai_toolkit brick is loaded (the
    decorator prefixes the brick name, so the plugin id is
    'gws_ai_toolkit.analytics'). When the brick is disabled this module is never
    imported, so the action disappears.
    """

    entity_action_type = EntityActionType.RESOURCE

    OPEN_ACTION = "open_in_analytics"

    def get_actions(self, entity: ResourceModel) -> list[EntityAction]:
        if not self._is_supported(entity):
            return []
        return [
            EntityAction.button(
                action_name=self.OPEN_ACTION,
                text="Open in Analytics",
                icon="bar_chart",
            )
        ]

    def execute_action(self, entity: ResourceModel, action_name: str) -> EntityActionResultDTO:
        if action_name != self.OPEN_ACTION:
            raise Exception(f"Unknown analytics action '{action_name}'")

        analytics_app = self._find_latest_analytics_app()
        if analytics_app is None:
            raise Exception(
                "No Constellab Analytics app found in this lab. "
                "Generate one first with the 'Generate Constellab Analytics app' task."
            )

        # navigate to the analytics app resource, passing the clicked resource
        # id so the app can load it
        resource_url = FrontService().get_resource_url(analytics_app.id)
        return EntityActionResultDTO(
            navigate_to=resource_url,
            navigate_query_params={ANALYTICS_APP_RESOURCE_QUERY_PARAM_KEY: entity.id},
            open_in_new_tab=True,
        )

    def _find_latest_analytics_app(self) -> ResourceModel | None:
        """Return the most recently created analytics app resource, or None.

        Analytics apps are identified by the tag added when they are generated
        (see :mod:`analytics_app_constants`). The search builder orders by
        creation date descending, so the first result is the latest.
        """
        search_builder = ResourceSearchBuilder()
        search_builder.add_tag_filter(Tag(ANALYTICS_APP_TAG_KEY, ANALYTICS_APP_TAG_VALUE))
        return search_builder.search_first()

    def _is_supported(self, entity: ResourceModel) -> bool:
        """Cheap, in-memory check: is this resource a Table or a CSV/TSV file."""
        resource_type = entity.get_resource_type()
        if resource_type is None:
            return False

        if Utils.issubclass(resource_type, Table):
            return True

        if Utils.issubclass(resource_type, File) and entity.fs_node_model is not None:
            return FileHelper.is_csv_or_excel(entity.fs_node_model.path)

        return False
