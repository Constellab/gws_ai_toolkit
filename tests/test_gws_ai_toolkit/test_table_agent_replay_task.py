"""
Unit tests for TableAgentReplay task
"""

import unittest

import pandas as pd
from gws_ai_toolkit.core.agents.table.table_agent_replay_task import TableAgentReplayTask
from gws_core import ResourceSet, Table, TaskRunner


# test_table_agent_replay_task
class TestTableAgentReplayTask(unittest.TestCase):
    """Test suite for TableAgentReplay task"""

    def test_table_agent_replay_task(self):
        """Test the TableAgentReplay task with a sample transformation sequence"""

        # These events were generated using test_table_agent_ai.TestTableAgentAiIntegration.test_transform_delegation_add_column
        # They represent a sequence of operations: rename column, then create scatter plot
        # Now structured as a list of AgentEventListDTOConv objects
        conversations = [
            {
                "user_query": {
                    "query": "Rename the column 'hello' to 'x_values' and create a scatter plot",
                    "agent_id": "7aa25334-2d6a-4101-8463-3ce9a513c08e",
                    "table_keys": ["test_data"],
                    "output_table_names": None,
                },
                "events": [
                    {
                        "response_id": "resp_0995956101a8e8bc006929d00f447c8199aa404f9893eee87d",
                        "agent_id": "7aa25334-2d6a-4101-8463-3ce9a513c08e",
                        "call_id": "call_tvF42DN3FKG6d5kfFMgBdKrY",
                        "type": "function_call",
                        "function_name": "transform_table",
                        "arguments": {
                            "table_name": "test_data",
                            "output_table_name": "test_data_renamed",
                            "user_request": "Rename the column 'hello' to 'x_values'",
                        },
                    },
                    {
                        "response_id": "resp_0995956101a8e8bc006929d00f447c8199aa404f9893eee87d",
                        "agent_id": "eca776ce-5a88-470d-8ccc-40e8ff1a6d5e",
                        "type": "create_sub_agent",
                    },
                    {
                        "response_id": "resp_052c1ac9bd89d995006929d01c4e248198ba82174e8b2d0cd8",
                        "agent_id": "eca776ce-5a88-470d-8ccc-40e8ff1a6d5e",
                        "call_id": "call_2LCAO5LksnkgAqog7hQr9IBZ",
                        "type": "function_call",
                        "function_name": "transform_dataframe",
                        "arguments": {
                            "code": "# Rename the column 'hello' to 'x_values'\ntransformed_df = df.rename(columns={'hello': 'x_values'})",
                            "transformed_table_name": "test_data_renamed",
                        },
                    },
                    {
                        "response_id": "resp_052c1ac9bd89d995006929d01c4e248198ba82174e8b2d0cd8",
                        "agent_id": "eca776ce-5a88-470d-8ccc-40e8ff1a6d5e",
                        "type": "response_full_text",
                        "text": "",
                    },
                    {
                        "response_id": "resp_0995956101a8e8bc006929d00f447c8199aa404f9893eee87d",
                        "agent_id": "7aa25334-2d6a-4101-8463-3ce9a513c08e",
                        "call_id": "call_tvF42DN3FKG6d5kfFMgBdKrY",
                        "function_response": "Successfully transformed the DataFrame. Continue with next steps if needed.",
                        "type": "sub_agent_success",
                    },
                    {
                        "response_id": "resp_0995956101a8e8bc006929d00f447c8199aa404f9893eee87d",
                        "agent_id": "7aa25334-2d6a-4101-8463-3ce9a513c08e",
                        "type": "response_full_text",
                        "text": "",
                    },
                    {
                        "response_id": "resp_0995956101a8e8bc006929d0221d788199b5391a02377baa4b",
                        "agent_id": "7aa25334-2d6a-4101-8463-3ce9a513c08e",
                        "call_id": "call_uQgIOtLrHVGVela3HnQ3ppwV",
                        "type": "function_call",
                        "function_name": "generate_plot",
                        "arguments": {
                            "table_name": "test_data_renamed",
                            "user_request": "Create a scatter plot with 'x_values' as x-axis and 'y_values' as y-axis.",
                        },
                    },
                    {
                        "response_id": "resp_0995956101a8e8bc006929d0221d788199b5391a02377baa4b",
                        "agent_id": "cf0eaf88-e9e1-492d-9fa7-319693642617",
                        "type": "create_sub_agent",
                    },
                    {
                        "response_id": "resp_0ed3efc4702870bc006929d024cdf8819a806072069d7f1547",
                        "agent_id": "cf0eaf88-e9e1-492d-9fa7-319693642617",
                        "call_id": "call_taSZGVmktju6CNvDJlePv9AA",
                        "type": "function_call",
                        "function_name": "generate_plotly_figure",
                        "arguments": {
                            "code": "fig = go.Figure()\nfig.add_trace(go.Scatter(x=df['x_values'], y=df['y_values'], mode='markers', marker=dict(color='blue')))\nfig.update_layout(title='Scatter Plot of x_values vs y_values', xaxis_title='x_values', yaxis_title='y_values')"
                        },
                    },
                    {
                        "response_id": "resp_0ed3efc4702870bc006929d024cdf8819a806072069d7f1547",
                        "agent_id": "cf0eaf88-e9e1-492d-9fa7-319693642617",
                        "type": "response_full_text",
                        "text": "",
                    },
                    {
                        "response_id": "resp_0995956101a8e8bc006929d0221d788199b5391a02377baa4b",
                        "agent_id": "7aa25334-2d6a-4101-8463-3ce9a513c08e",
                        "call_id": "call_uQgIOtLrHVGVela3HnQ3ppwV",
                        "function_response": "Successfully generated the plot. Continue with next steps if needed.",
                        "type": "sub_agent_success",
                    },
                    {
                        "response_id": "resp_0995956101a8e8bc006929d0221d788199b5391a02377baa4b",
                        "agent_id": "7aa25334-2d6a-4101-8463-3ce9a513c08e",
                        "type": "response_full_text",
                        "text": "",
                    },
                ],
            }
        ]

        # Create input dataframe
        input_df = pd.DataFrame({"hello": [1, 2, 3, 4, 5], "y_values": [2, 4, 1, 8, 6]})

        # Create expected output dataframe (after column rename)
        expected_df = pd.DataFrame({"x_values": [1, 2, 3, 4, 5], "y_values": [2, 4, 1, 8, 6]})

        # Create input ResourceSet with the test table
        input_resource_set = ResourceSet()
        input_table = Table(input_df)
        input_table.name = "test_data"
        input_resource_set.add_resource(input_table, unique_name="test_data")

        # Run the task with conversations list
        # Since chat_messages is a DictParam but we're storing a list,
        # we just pass the list directly and DictParam will accept it as the raw dict value
        runner = TaskRunner(
            task_type=TableAgentReplayTask,
            params={"chat_messages": conversations},
            inputs={"input_resource_set": input_resource_set},
        )
        outputs = runner.run()

        # Validate outputs
        output_resource_set: ResourceSet = outputs["output_resource_set"]
        self.assertIsInstance(output_resource_set, ResourceSet)

        # Get output resources
        output_resources = output_resource_set.get_resources()

        # We should have only the transformed table (input tables are NOT included in output)
        self.assertEqual(len(output_resources), 1, "Should have exactly 1 transformed table in output")

        # Check that the renamed table exists
        self.assertIn("test_data_renamed", output_resources, "Output should contain 'test_data_renamed' table")

        # Verify that the original input table is NOT in the output
        self.assertNotIn("test_data", output_resources, "Input table 'test_data' should NOT be in output")

        # Validate the transformed table
        renamed_table = output_resources["test_data_renamed"]
        self.assertIsInstance(renamed_table, Table)

        # Check the dataframe structure and content
        renamed_df = renamed_table.to_dataframe()
        pd.testing.assert_frame_equal(renamed_df.reset_index(drop=True), expected_df)

        # Verify column names
        self.assertIn("x_values", renamed_df.columns, "Renamed table should have 'x_values' column")
        self.assertNotIn("hello", renamed_df.columns, "Renamed table should not have 'hello' column")
        self.assertIn("y_values", renamed_df.columns, "Renamed table should have 'y_values' column")
