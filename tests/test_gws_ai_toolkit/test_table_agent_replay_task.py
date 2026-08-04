"""
Unit tests for TableAgentReplay task
"""

import unittest

import pandas as pd
from gws_ai_toolkit.core.agents.table.table_agent_replay_task import TableAgentReplayTask
from gws_core import (
    InputSpec,
    InputSpecs,
    OutputSpec,
    OutputSpecs,
    ResourceList,
    ResourceSet,
    Table,
    TaskRunner,
)

MAIN_AGENT = "7aa25334-2d6a-4101-8463-3ce9a513c08e"
TRANSFORM_AGENT = "eca776ce-5a88-470d-8ccc-40e8ff1a6d5e"
PLOT_AGENT = "cf0eaf88-e9e1-492d-9fa7-319693642617"

MAIN_TRANSFORM_RESPONSE = "resp_main_transform"
SUB_TRANSFORM_RESPONSE = "resp_sub_transform"
MAIN_PLOT_RESPONSE = "resp_main_plot"
SUB_PLOT_RESPONSE = "resp_sub_plot"


# test_table_agent_replay_task
class TestTableAgentReplayTask(unittest.TestCase):
    """Test suite for TableAgentReplay task.

    Replaying re-executes the recorded tool calls without contacting a model, so this test
    makes no API call.
    """

    def _serialized_events(self) -> list[dict]:
        """Build the recorded event sequence to replay.

        The sequence is a flat list of serialized table agent events: a user query, then for
        each operation the main agent's function call, the sub-agent it created, the
        sub-agent's own function call, and the success reported back at the main agent's level.

        Two user queries are recorded, one per operation. The replay only refreshes the tables
        available to a query between queries, so the plot has to be its own turn to see the
        table the first turn produced.

        Returns:
            The serialized events, as the task's config expects them.
        """
        return [
            {
                "type": "user_tables",
                "query": "Rename the column 'hello' to 'x_values'",
                "agent_id": MAIN_AGENT,
                "table_keys": ["test_data"],
                "output_table_names": None,
            },
            # --- Turn 1: rename a column, delegated to the transform sub-agent.
            {
                "type": "function_call",
                "response_id": MAIN_TRANSFORM_RESPONSE,
                "agent_id": MAIN_AGENT,
                "call_id": "call_main_transform",
                "function_name": "transform_table",
                "arguments": {
                    "table_name": "test_data",
                    "output_table_name": "test_data_renamed",
                    "user_request": "Rename the column 'hello' to 'x_values'",
                },
            },
            {
                "type": "create_sub_agent",
                "response_id": MAIN_TRANSFORM_RESPONSE,
                "agent_id": TRANSFORM_AGENT,
            },
            {
                "type": "function_call",
                "response_id": SUB_TRANSFORM_RESPONSE,
                "agent_id": TRANSFORM_AGENT,
                "call_id": "call_sub_transform",
                "function_name": "transform_dataframe",
                "arguments": {
                    "code": (
                        "# Rename the column 'hello' to 'x_values'\n"
                        "transformed_df = df.rename(columns={'hello': 'x_values'})"
                    ),
                    "transformed_table_name": "test_data_renamed",
                },
            },
            {
                "type": "response_full_text",
                "response_id": SUB_TRANSFORM_RESPONSE,
                "agent_id": TRANSFORM_AGENT,
                "text": "",
            },
            {
                "type": "sub_agent_success",
                "response_id": MAIN_TRANSFORM_RESPONSE,
                "agent_id": MAIN_AGENT,
                "call_id": "call_main_transform",
                "function_response": (
                    "Successfully transformed the DataFrame. Continue with next steps if needed."
                ),
            },
            {
                "type": "response_full_text",
                "response_id": MAIN_TRANSFORM_RESPONSE,
                "agent_id": MAIN_AGENT,
                "text": "",
            },
            # --- Turn 2: plot the table the first turn produced.
            {
                "type": "user_tables",
                "query": "Create a scatter plot of x_values against y_values",
                "agent_id": MAIN_AGENT,
                "table_keys": ["test_data_renamed"],
                "output_table_names": None,
            },
            {
                "type": "function_call",
                "response_id": MAIN_PLOT_RESPONSE,
                "agent_id": MAIN_AGENT,
                "call_id": "call_main_plot",
                "function_name": "generate_plot",
                "arguments": {
                    "table_name": "test_data_renamed",
                    "user_request": (
                        "Create a scatter plot with 'x_values' as x-axis and 'y_values' as y-axis."
                    ),
                },
            },
            {
                "type": "create_sub_agent",
                "response_id": MAIN_PLOT_RESPONSE,
                "agent_id": PLOT_AGENT,
            },
            {
                "type": "function_call",
                "response_id": SUB_PLOT_RESPONSE,
                "agent_id": PLOT_AGENT,
                "call_id": "call_sub_plot",
                "function_name": "generate_plotly_figure",
                "arguments": {
                    "code": (
                        "fig = go.Figure()\n"
                        "fig.add_trace(go.Scatter(x=df['x_values'], y=df['y_values'], "
                        "mode='markers'))"
                    ),
                    "plot_name": "Scatter Plot Of X Values Versus Y Values",
                },
            },
            {
                "type": "response_full_text",
                "response_id": SUB_PLOT_RESPONSE,
                "agent_id": PLOT_AGENT,
                "text": "",
            },
            {
                "type": "sub_agent_success",
                "response_id": MAIN_PLOT_RESPONSE,
                "agent_id": MAIN_AGENT,
                "call_id": "call_main_plot",
                "function_response": (
                    "Successfully generated the plot. Continue with next steps if needed."
                ),
            },
            {
                "type": "response_full_text",
                "response_id": MAIN_PLOT_RESPONSE,
                "agent_id": MAIN_AGENT,
                "text": "",
            },
        ]

    def test_table_agent_replay_task(self):
        """Replaying a recorded run reproduces its transformed table and its plot."""
        input_df = pd.DataFrame({"hello": [1, 2, 3, 4, 5], "y_values": [2, 4, 1, 8, 6]})
        expected_df = pd.DataFrame({"x_values": [1, 2, 3, 4, 5], "y_values": [2, 4, 1, 8, 6]})

        input_table = Table(input_df)
        input_table.name = "test_data"
        resource_list = ResourceList([input_table])

        runner = TaskRunner(
            task_type=TableAgentReplayTask,
            inputs={"source": resource_list},
            params={
                "serialized_events": self._serialized_events(),
                "model": "openai:gpt-4o",
                "temperature": 0.1,
            },
            # Needed to make dynamic io work with the task runner.
            input_specs=InputSpecs({"source": InputSpec(ResourceList)}),
            output_specs=OutputSpecs({"output_resource_set": OutputSpec(ResourceSet)}),
        )
        outputs = runner.run()

        output_resource_set: ResourceSet = outputs["output_resource_set"]
        self.assertIsInstance(output_resource_set, ResourceSet)

        output_resources = output_resource_set.get_resources()

        # The transformed table plus the generated plot; the input table is not included.
        self.assertIn(
            "test_data_renamed", output_resources, "Output should contain 'test_data_renamed' table"
        )
        self.assertNotIn(
            "test_data", output_resources, "Input table 'test_data' should NOT be in output"
        )

        renamed_table = output_resources["test_data_renamed"]
        self.assertIsInstance(renamed_table, Table)

        renamed_df = renamed_table.to_dataframe()
        pd.testing.assert_frame_equal(renamed_df.reset_index(drop=True), expected_df)

        self.assertIn("x_values", renamed_df.columns, "Renamed table should have 'x_values' column")
        self.assertNotIn(
            "hello", renamed_df.columns, "Renamed table should not have 'hello' column"
        )
        self.assertIn("y_values", renamed_df.columns, "Renamed table should have 'y_values' column")

        # The replayed plot is produced too, so a saved chat restores its figures as well.
        self.assertEqual(
            len(output_resources), 2, "Should have the transformed table and the plot in output"
        )


if __name__ == "__main__":
    unittest.main()
