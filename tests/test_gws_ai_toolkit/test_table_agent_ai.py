import os
from typing import cast

import pandas as pd
from gws_ai_toolkit.core.agents.table.multi_table_agent_ai_events import MultiTableTransformEvent
from gws_ai_toolkit.core.agents.table.plotly_agent_ai_events import PlotGeneratedEvent
from gws_ai_toolkit.core.agents.table.table_agent_ai import TableAgentAi
from gws_ai_toolkit.core.agents.table.table_agent_ai_events import UserQueryMultiTablesEvent
from gws_ai_toolkit.core.agents.table.table_agent_ai_service import TableAgentAiService
from gws_ai_toolkit.core.agents.table.table_transform_agent_ai_events import TableTransformEvent
from gws_core import BaseTestCase, ResourceSet, Table


# test_table_agent_ai
class TestTableAgentAiIntegration(BaseTestCase):
    """Integration test using real OpenAI API"""

    def test_plot_delegation_scatter_plot(self):
        """Test that TableAgentAi correctly delegates plot requests to PlotlyAgentAi"""
        # Create simple dataframe with two numeric columns
        test_dataframe = pd.DataFrame({"hello": [1, 2, 3, 4, 5], "y_values": [2, 4, 1, 8, 6]})
        expected_df = pd.DataFrame({"x_values": [1, 2, 3, 4, 5], "y_values": [2, 4, 1, 8, 6]})

        # Create TableAgentAi instance without tables
        agent = TableAgentAi(
            openai_api_key=os.getenv("OPENAI_API_KEY", ""),
            model="gpt-4o",  # Use cheaper model for testing
            temperature=0.1,
        )

        # Create user query with tables
        tables = {"test_data": Table(test_dataframe)}
        user_query = UserQueryMultiTablesEvent(
            query="Can you rename the column 'hello' to 'x_values', then make a scatter plot with column x_values as x and column y_values as y",
            tables=tables,
            agent_id=agent.id,
        )

        events = list(agent.call_agent(user_query))

        transform_events = [e for e in events if isinstance(e, TableTransformEvent)]
        self.assertEqual(len(transform_events), 1)

        resulted_df = transform_events[0].table.to_dataframe()
        pd.testing.assert_frame_equal(resulted_df.reset_index(drop=True), expected_df)

        # Check the plot
        plot_events = [e for e in events if isinstance(e, PlotGeneratedEvent)]
        self.assertEqual(len(plot_events), 1)

        self._test_table_agent_ai_service(
            agent,
            expected_tables={transform_events[0].table_name: Table(expected_df)},
            expected_plots=1,
        )

    def test_transform_delegation_add_column(self):
        """Test that TableAgentAi correctly delegates transform requests to TableTransformAgentAi"""
        # Create simple dataframe with two numeric columns
        test_dataframe = pd.DataFrame({"hello": [1, 2, 3, 4, 5], "y_values": [2, 4, 1, 8, 6]})

        # Create TableAgentAi instance without tables
        agent = TableAgentAi(
            openai_api_key=os.getenv("OPENAI_API_KEY", ""),
            model="gpt-4o",  # Use cheaper model for testing
            temperature=0.1,
        )

        # Create user query with tables for first call
        tables = {"test_data": Table(test_dataframe)}
        user_query = UserQueryMultiTablesEvent(
            query="Rename the column 'hello' to 'x_values'",
            tables=tables,
            agent_id=agent.id,
        )

        events = list(agent.call_agent(user_query))

        transform_events = [e for e in events if isinstance(e, TableTransformEvent)]
        self.assertEqual(len(transform_events), 1)

        # Check the dataframe output after first agent call
        transform_event = transform_events[0]
        transformed_df = transform_event.table.to_dataframe()

        expected_df = pd.DataFrame({"x_values": [1, 2, 3, 4, 5], "y_values": [2, 4, 1, 8, 6]})
        pd.testing.assert_frame_equal(transformed_df.reset_index(drop=True), expected_df)

        # Get the output tables from agent (includes the transformed table)
        output_tables = agent.get_output_tables()

        # Create user query with updated tables for second call
        # Use the transformed table for the plot
        tables_for_plot = {transform_event.table_name: output_tables[transform_event.table_name]}
        user_query2 = UserQueryMultiTablesEvent(
            query="Now make a scatter plot with column x_values as x and column y_values as y",
            tables=tables_for_plot,
            agent_id=agent.id,
        )

        events = list(agent.call_agent(user_query2))
        plot_events = [e for e in events if isinstance(e, PlotGeneratedEvent)]
        self.assertEqual(len(plot_events), 1)

        self._test_table_agent_ai_service(
            agent,
            expected_tables={transform_event.table_name: Table(expected_df)},
            expected_plots=1,
        )

    def test_multiple_operations_in_single_call(self):
        """Test that when multiple operations are requested in one call, both transformations are executed"""
        # Create first dataframe - sales data
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

        # Create TableAgentAi instance without tables
        agent = TableAgentAi(
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
            agent_id=agent.id,
        )

        # Request both operations in a single call
        events = list(agent.call_agent(user_query))

        # The agent should perform BOTH operations
        transform_events = [e for e in events if isinstance(e, TableTransformEvent)]
        self.assertEqual(len(transform_events), 2, "Should have TWO transform events (both operations)")

        # Get output tables from agent
        output_tables = agent.get_output_tables()

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

        self._test_table_agent_ai_service(
            agent,
            expected_tables={
                "high_sales_data": Table(high_sales_df),
                "low_stock_data": Table(low_stock_df),
            },
        )

    def test_multi_table_transformation(self):
        """Test that the agent can perform multi-table transformations (merge/join operations)"""
        # Create first dataframe - sales data
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

        # Create TableAgentAi instance without tables
        agent = TableAgentAi(
            openai_api_key=os.getenv("OPENAI_API_KEY", ""),
            model="gpt-4o",
            temperature=0.1,
        )

        # Create user query with both tables
        tables = {"sales_data": Table(sales_df), "inventory_data": Table(inventory_df)}
        user_query = UserQueryMultiTablesEvent(
            query=(
                "Merge the sales_data and inventory_data tables on the 'product' column "
                "and name the result 'combined_data'."
            ),
            tables=tables,
            agent_id=agent.id,
        )

        # Request a multi-table operation (merge)
        events = list(agent.call_agent(user_query))

        # The agent should perform a multi-table transformation
        multi_table_events = [e for e in events if isinstance(e, MultiTableTransformEvent)]
        self.assertEqual(len(multi_table_events), 1, "Should have ONE multi-table transform event")

        # Get output tables from agent
        output_tables = agent.get_output_tables()

        # Verify the merged table was created
        self.assertIn("combined_data", output_tables, "combined_data should be created")

        # Verify the merged table has the expected structure
        combined_table = output_tables["combined_data"]
        combined_df = combined_table.get_data()

        # Should have columns from both tables
        expected_columns = ["product", "sales", "region", "stock", "warehouse"]
        for col in expected_columns:
            self.assertIn(col, combined_df.columns, f"Column {col} should be in combined table")

        # Should have 5 rows (all products matched)
        self.assertEqual(len(combined_df), 5, "Should have 5 rows after merge")

        self._test_table_agent_ai_service(
            agent,
            expected_tables={"combined_data": Table(combined_df)},
        )

    def _test_table_agent_ai_service(
        self, agent: TableAgentAi, expected_tables: dict[str, Table], expected_plots: int = 0
    ):
        resource_model = TableAgentAiService.save_table_agent_ai(
            table_agent_ai=agent,
        )

        resource = cast(ResourceSet, resource_model.get_resource())
        self.assertIsInstance(resource, ResourceSet)

        self.assertEqual(len(resource.get_resources()), len(expected_tables) + expected_plots)

        for table_name, expected_table in expected_tables.items():
            self.assertIn(table_name, resource.get_resources())

            table = cast(Table, resource.get_resource(table_name))
            self.assertIsInstance(table, Table)

            df = table.to_dataframe()
            pd.testing.assert_frame_equal(
                df.reset_index(drop=True), expected_table.to_dataframe().reset_index(drop=True)
            )
