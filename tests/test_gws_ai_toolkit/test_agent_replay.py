import os
import unittest

import pandas as pd
from gws_ai_toolkit.core.agents.base_function_agent_events import BaseFunctionWithSubAgentEvent
from gws_ai_toolkit.core.agents.plotly_agent_ai_events import PlotGeneratedEvent
from gws_ai_toolkit.core.agents.table_agent_ai import TableAgentAi
from gws_ai_toolkit.core.agents.table_transform_agent_ai_events import TableTransformEvent
from gws_core import Table
from pydantic import TypeAdapter


# test_agent_replay
class TestTableAgentAiIntegration(unittest.TestCase):
    def test_agent_replay(self):
        # Theses event were generated using test_table_agent_ai.TestTableAgentAiIntegration.test_transform_delegation_add_column
        events = [
            {
                "response_id": "resp_0995956101a8e8bc006929d00f447c8199aa404f9893eee87d",
                "agent_id": "7aa25334-2d6a-4101-8463-3ce9a513c08e",
                "type": "response_created",
            },
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
                "type": "response_created",
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
                "response_id": "resp_052c1ac9bd89d995006929d01c4e248198ba82174e8b2d0cd8",
                "agent_id": "eca776ce-5a88-470d-8ccc-40e8ff1a6d5e",
                "type": "response_completed",
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
                "response_id": "resp_0995956101a8e8bc006929d00f447c8199aa404f9893eee87d",
                "agent_id": "7aa25334-2d6a-4101-8463-3ce9a513c08e",
                "type": "response_completed",
            },
            {
                "response_id": "resp_0995956101a8e8bc006929d01f4d1c8199947c55e50555c54a",
                "agent_id": "7aa25334-2d6a-4101-8463-3ce9a513c08e",
                "type": "response_created",
            },
            {
                "response_id": "resp_0995956101a8e8bc006929d01f4d1c8199947c55e50555c54a",
                "agent_id": "7aa25334-2d6a-4101-8463-3ce9a513c08e",
                "type": "response_full_text",
                "text": "The column 'hello' has been successfully renamed to 'x_values' in the table. If you need any further operations, feel free to let me know!",
            },
            {
                "response_id": "resp_0995956101a8e8bc006929d01f4d1c8199947c55e50555c54a",
                "agent_id": "7aa25334-2d6a-4101-8463-3ce9a513c08e",
                "type": "response_completed",
            },
            {
                "response_id": "resp_0995956101a8e8bc006929d0221d788199b5391a02377baa4b",
                "agent_id": "7aa25334-2d6a-4101-8463-3ce9a513c08e",
                "type": "response_created",
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
                "type": "response_created",
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
                "response_id": "resp_0ed3efc4702870bc006929d024cdf8819a806072069d7f1547",
                "agent_id": "cf0eaf88-e9e1-492d-9fa7-319693642617",
                "type": "response_completed",
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
            {
                "response_id": "resp_0995956101a8e8bc006929d0221d788199b5391a02377baa4b",
                "agent_id": "7aa25334-2d6a-4101-8463-3ce9a513c08e",
                "type": "response_completed",
            },
            {
                "response_id": "resp_0995956101a8e8bc006929d02752c88199957eb2e3e3ecc148",
                "agent_id": "7aa25334-2d6a-4101-8463-3ce9a513c08e",
                "type": "response_created",
            },
            {
                "response_id": "resp_0995956101a8e8bc006929d02752c88199957eb2e3e3ecc148",
                "agent_id": "7aa25334-2d6a-4101-8463-3ce9a513c08e",
                "type": "response_full_text",
                "text": "The scatter plot with 'x_values' as the x-axis and 'y_values' as the y-axis has been successfully created. If there's anything else you need, just let me know!",
            },
            {
                "response_id": "resp_0995956101a8e8bc006929d02752c88199957eb2e3e3ecc148",
                "agent_id": "7aa25334-2d6a-4101-8463-3ce9a513c08e",
                "type": "response_completed",
            },
        ]

        adapter = TypeAdapter(BaseFunctionWithSubAgentEvent)

        event_objects = [adapter.validate_python(m) for m in events]

        # Create simple dataframe with two numeric columns
        input_df = pd.DataFrame({"hello": [1, 2, 3, 4, 5], "y_values": [2, 4, 1, 8, 6]})
        expected_df = pd.DataFrame({"x_values": [1, 2, 3, 4, 5], "y_values": [2, 4, 1, 8, 6]})

        replay_agent = TableAgentAi(
            openai_api_key=os.getenv("OPENAI_API_KEY", ""),
            model="gpt-4o",
            temperature=0.1,
            table=Table(input_df),
            table_unique_name="test_data",
        )

        # Replay the previous events
        replayed_events = list(replay_agent.replay_events(event_objects))

        # Check that we have the same number of transform events
        replay_transform_events = [e for e in replayed_events if isinstance(e, TableTransformEvent)]
        self.assertEqual(len(replay_transform_events), 1)

        # Check we have the same output dataframe
        replayed_transformed_df = replay_transform_events[0].table.to_dataframe()
        pd.testing.assert_frame_equal(replayed_transformed_df.reset_index(drop=True), expected_df)

        # check the plot events
        replay_plot_events = [e for e in replayed_events if isinstance(e, PlotGeneratedEvent)]
        self.assertEqual(len(replay_plot_events), 1)
