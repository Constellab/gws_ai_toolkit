import os
import unittest

import pandas as pd
from gws_ai_toolkit.core.agents.base_function_agent_events import BaseFunctionWithSubAgentEvent
from gws_ai_toolkit.core.agents.table.table_agent_ai import TableAgentAi
from gws_ai_toolkit.core.agents.table.table_agent_event_base import UserQueryMultiTablesEvent
from gws_ai_toolkit.core.agents.table.table_transform_agent_ai_events import TableTransformEvent
from gws_core import Table
from pydantic import TypeAdapter


# test_agent_replay
class TestTableAgentAiIntegration(unittest.TestCase):
    def test_agent_replay(self):
        # Theses event were generated using test_table_agent_ai.TestTableAgentAiIntegration.test_multiple_operations_in_single_call
        events = [
            {
                "response_id": "resp_0f70229ae8361f7c00692eed37b900819abe73637fca270732",
                "agent_id": "6d3a8f24-f252-48a3-bb2e-d9c15971dc31",
                "type": "response_created",
            },
            {
                "response_id": "resp_0f70229ae8361f7c00692eed37b900819abe73637fca270732",
                "agent_id": "6d3a8f24-f252-48a3-bb2e-d9c15971dc31",
                "call_id": "call_6xonMtp0Hxx2aOD3w6mHJQWw",
                "type": "function_call",
                "function_name": "transform_table",
                "arguments": {
                    "table_name": "sales_data",
                    "output_table_name": "high_sales_data",
                    "user_request": "Filter to only include products with sales greater than 150.",
                },
            },
            {
                "response_id": "resp_0f70229ae8361f7c00692eed37b900819abe73637fca270732",
                "agent_id": "62fa8f41-99d8-4610-afc5-8eaf6c6c694b",
                "type": "create_sub_agent",
            },
            {
                "response_id": "resp_0312f8cec9b3a12b00692eed3a2198819aaee9517c0fadc9e9",
                "agent_id": "62fa8f41-99d8-4610-afc5-8eaf6c6c694b",
                "type": "response_created",
            },
            {
                "response_id": "resp_0312f8cec9b3a12b00692eed3a2198819aaee9517c0fadc9e9",
                "agent_id": "62fa8f41-99d8-4610-afc5-8eaf6c6c694b",
                "call_id": "call_gqADzH2lEuu6JN9dThd1Oyur",
                "type": "function_call",
                "function_name": "transform_dataframe",
                "arguments": {
                    "code": "# Filter rows where sales are greater than 150\ntransformed_df = df[df['sales'] > 150]",
                    "transformed_table_name": "high_sales_data",
                },
            },
            {
                "response_id": "resp_0312f8cec9b3a12b00692eed3a2198819aaee9517c0fadc9e9",
                "agent_id": "62fa8f41-99d8-4610-afc5-8eaf6c6c694b",
                "type": "response_full_text",
                "text": "",
            },
            {
                "response_id": "resp_0312f8cec9b3a12b00692eed3a2198819aaee9517c0fadc9e9",
                "agent_id": "62fa8f41-99d8-4610-afc5-8eaf6c6c694b",
                "type": "response_completed",
            },
            {
                "response_id": "resp_0f70229ae8361f7c00692eed37b900819abe73637fca270732",
                "agent_id": "6d3a8f24-f252-48a3-bb2e-d9c15971dc31",
                "call_id": "call_6xonMtp0Hxx2aOD3w6mHJQWw",
                "function_response": "Successfully transformed the DataFrame. Continue with next steps if needed.",
                "type": "sub_agent_success",
            },
            {
                "response_id": "resp_0f70229ae8361f7c00692eed37b900819abe73637fca270732",
                "agent_id": "6d3a8f24-f252-48a3-bb2e-d9c15971dc31",
                "type": "response_full_text",
                "text": "",
            },
            {
                "response_id": "resp_0f70229ae8361f7c00692eed37b900819abe73637fca270732",
                "agent_id": "6d3a8f24-f252-48a3-bb2e-d9c15971dc31",
                "type": "response_completed",
            },
            {
                "response_id": "resp_0f70229ae8361f7c00692eed3cb410819a9854da4f5e0aa81d",
                "agent_id": "6d3a8f24-f252-48a3-bb2e-d9c15971dc31",
                "type": "response_created",
            },
            {
                "response_id": "resp_0f70229ae8361f7c00692eed3cb410819a9854da4f5e0aa81d",
                "agent_id": "6d3a8f24-f252-48a3-bb2e-d9c15971dc31",
                "call_id": "call_PlW6qh8ZKE528Lb6e9zwRoG5",
                "type": "function_call",
                "function_name": "transform_table",
                "arguments": {
                    "table_name": "inventory_data",
                    "output_table_name": "low_stock_data",
                    "user_request": "Filter to only include products with stock less than 50.",
                },
            },
            {
                "response_id": "resp_0f70229ae8361f7c00692eed3cb410819a9854da4f5e0aa81d",
                "agent_id": "4c1e2bef-19d4-4373-b62c-f81a1b3b2111",
                "type": "create_sub_agent",
            },
            {
                "response_id": "resp_00c9bf13992df69200692eed3f42848190b51ffdd816d34995",
                "agent_id": "4c1e2bef-19d4-4373-b62c-f81a1b3b2111",
                "type": "response_created",
            },
            {
                "response_id": "resp_00c9bf13992df69200692eed3f42848190b51ffdd816d34995",
                "agent_id": "4c1e2bef-19d4-4373-b62c-f81a1b3b2111",
                "call_id": "call_OX8O5RqZL5aCskZbLZtZEzqk",
                "type": "function_call",
                "function_name": "transform_dataframe",
                "arguments": {
                    "code": "# Filter products with stock less than 50\ntransformed_df = df[df['stock'] < 50]",
                    "transformed_table_name": "low_stock_data",
                },
            },
            {
                "response_id": "resp_00c9bf13992df69200692eed3f42848190b51ffdd816d34995",
                "agent_id": "4c1e2bef-19d4-4373-b62c-f81a1b3b2111",
                "type": "response_full_text",
                "text": "",
            },
            {
                "response_id": "resp_00c9bf13992df69200692eed3f42848190b51ffdd816d34995",
                "agent_id": "4c1e2bef-19d4-4373-b62c-f81a1b3b2111",
                "type": "response_completed",
            },
            {
                "response_id": "resp_0f70229ae8361f7c00692eed3cb410819a9854da4f5e0aa81d",
                "agent_id": "6d3a8f24-f252-48a3-bb2e-d9c15971dc31",
                "call_id": "call_PlW6qh8ZKE528Lb6e9zwRoG5",
                "function_response": "Successfully transformed the DataFrame. Continue with next steps if needed.",
                "type": "sub_agent_success",
            },
            {
                "response_id": "resp_0f70229ae8361f7c00692eed3cb410819a9854da4f5e0aa81d",
                "agent_id": "6d3a8f24-f252-48a3-bb2e-d9c15971dc31",
                "type": "response_full_text",
                "text": "",
            },
            {
                "response_id": "resp_0f70229ae8361f7c00692eed3cb410819a9854da4f5e0aa81d",
                "agent_id": "6d3a8f24-f252-48a3-bb2e-d9c15971dc31",
                "type": "response_completed",
            },
            {
                "response_id": "resp_0f70229ae8361f7c00692eed41dfe0819a84382c22bd83d114",
                "agent_id": "6d3a8f24-f252-48a3-bb2e-d9c15971dc31",
                "type": "response_created",
            },
            {
                "response_id": "resp_0f70229ae8361f7c00692eed41dfe0819a84382c22bd83d114",
                "agent_id": "6d3a8f24-f252-48a3-bb2e-d9c15971dc31",
                "type": "response_full_text",
                "text": "Both transformations are complete:\\n\\n- **high_sales_data**: Filtered to include products with sales greater than 150.\\n- **low_stock_data**: Filtered to include products with stock less than 50.\\n\\nIf you need further operations or visualizations, feel free to ask!",
            },
            {
                "response_id": "resp_0f70229ae8361f7c00692eed41dfe0819a84382c22bd83d114",
                "agent_id": "6d3a8f24-f252-48a3-bb2e-d9c15971dc31",
                "type": "response_completed",
            },
        ]

        adapter = TypeAdapter(BaseFunctionWithSubAgentEvent)

        event_objects = [adapter.validate_python(m) for m in events]

        sales_df = pd.DataFrame(
            {
                "product": ["A", "B", "C", "D", "E"],
                "sales": [100, 200, 150, 300, 250],
                "region": ["North", "South", "North", "West", "East"],
            }
        )

        # Create second dataframe - inventory data
        inventory_df = pd.DataFrame(
            {
                "product": ["A", "B", "C", "D", "E"],
                "stock": [50, 30, 80, 20, 60],
                "warehouse": ["W1", "W2", "W1", "W3", "W2"],
            }
        )
        # add user_message to event
        replay_agent = TableAgentAi(
            openai_api_key=os.getenv("OPENAI_API_KEY", ""),
            model="gpt-4o",
            temperature=0.1,
        )

        # Create user query with both tables
        tables = {"sales_data": Table(sales_df), "inventory_data": Table(inventory_df)}
        user_query = UserQueryMultiTablesEvent(
            query=(
                "Filter the sales_data table to only include products with sales greater than 150 "
                "and name it 'high_sales_data'. Also filter the inventory_data table to only include "
                "products with stock less than 50 and name it 'low_stock_data'."
            ),
            tables=tables,
            agent_id=replay_agent.id,
        )
        # Replay the previous events
        replayed_events = list(replay_agent.replay_events(event_objects, user_query))

        # The agent should perform BOTH operations
        transform_events = [e for e in replayed_events if isinstance(e, TableTransformEvent)]
        self.assertEqual(len(transform_events), 2, "Should have TWO transform events (both operations)")

        # Get output tables from agent
        output_tables = replay_agent.get_output_tables()

        # Verify both tables were created
        self.assertIn("high_sales_data", output_tables, "high_sales_data should be created")
        self.assertIn("low_stock_data", output_tables, "low_stock_data should be created")

        # Verify the first transformation was correct
        high_sales_table = output_tables["high_sales_data"]
        high_sales_df = high_sales_table.get_data()
        self.assertTrue(all(high_sales_df["sales"] > 150), "All sales should be > 150")
        self.assertEqual(len(high_sales_df), 3, "Should have 3 products with sales > 150")

        # Verify the second transformation was correct
        low_stock_table = output_tables["low_stock_data"]
        low_stock_df = low_stock_table.get_data()
        self.assertTrue(all(low_stock_df["stock"] < 50), "All stock should be < 50")
        self.assertEqual(len(low_stock_df), 2, "Should have 2 products with stock < 50")
