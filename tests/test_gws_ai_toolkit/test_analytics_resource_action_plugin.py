from gws_ai_toolkit.apps.ai_table_standalone_app.analytics_app_constants import (
    ANALYTICS_APP_TAG_KEY,
    ANALYTICS_APP_TAG_VALUE,
)
from gws_ai_toolkit.apps.ai_table_standalone_app.analytics_resource_action_plugin import (
    AnalyticsResourceActionPlugin,
)
from gws_core import BaseTestCase, ReflexResource, Tag
from gws_core.core.service.front_service import FrontService
from gws_core.entity_action.entity_action import EntityActionKind
from gws_core.impl.robot.robot_resource import Robot
from gws_core.impl.table.table import Table
from gws_core.resource.resource_dto import ResourceOrigin
from gws_core.resource.resource_model import ResourceModel


# test_analytics_resource_action_plugin
class TestAnalyticsResourceActionPlugin(BaseTestCase):

    def test_get_actions_for_table(self):
        plugin = AnalyticsResourceActionPlugin()

        # a Table resource gets the 'Open in Analytics' action
        table_model = ResourceModel.save_from_resource(
            Table(), origin=ResourceOrigin.UPLOADED
        )
        actions = plugin.get_actions(table_model)
        self.assertEqual(len(actions), 1)
        self.assertEqual(actions[0].kind, EntityActionKind.BUTTON)
        self.assertEqual(actions[0].action_name, AnalyticsResourceActionPlugin.OPEN_ACTION)
        self.assertEqual(actions[0].text, "Open in Analytics")

    def test_get_actions_for_unsupported_resource(self):
        plugin = AnalyticsResourceActionPlugin()

        # a non-table, non-csv resource gets no action
        robot_model = ResourceModel.save_from_resource(
            Robot.empty(), origin=ResourceOrigin.UPLOADED
        )
        self.assertEqual(plugin.get_actions(robot_model), [])

    def test_execute_action_without_analytics_app(self):
        plugin = AnalyticsResourceActionPlugin()

        table_model = ResourceModel.save_from_resource(
            Table(), origin=ResourceOrigin.UPLOADED
        )

        # no analytics app generated yet -> the action raises
        with self.assertRaisesRegex(Exception, "No Constellab Analytics app"):
            plugin.execute_action(table_model, AnalyticsResourceActionPlugin.OPEN_ACTION)

    def test_execute_action_navigates_to_analytics_app(self):
        plugin = AnalyticsResourceActionPlugin()

        table_model = ResourceModel.save_from_resource(
            Table(), origin=ResourceOrigin.UPLOADED
        )

        # an analytics app resource (identified by its tag)
        analytics_app = ReflexResource()
        analytics_app.tags.add_tag(Tag(ANALYTICS_APP_TAG_KEY, ANALYTICS_APP_TAG_VALUE))
        analytics_app_model = ResourceModel.save_from_resource(
            analytics_app, origin=ResourceOrigin.UPLOADED
        )

        result = plugin.execute_action(
            table_model, AnalyticsResourceActionPlugin.OPEN_ACTION
        )

        # navigate to the analytics app, passing the clicked resource id
        self.assertEqual(
            result.navigate_to, FrontService().get_resource_url(analytics_app_model.id)
        )
        self.assertEqual(result.navigate_query_params, {"resourceId": table_model.id})
