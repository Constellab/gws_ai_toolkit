import os
import unittest

import pandas as pd
from gws_ai_toolkit.core.agents.multi_table_agent_ai_events import MultiTableTransformEvent
from gws_ai_toolkit.core.agents.plotly_agent_ai_events import PlotGeneratedEvent
from gws_ai_toolkit.core.agents.table_agent_ai import TableAgentAi
from gws_ai_toolkit.core.agents.table_transform_agent_ai_events import TableTransformEvent
from gws_core import Table


# test_table_agent_ai
class TestTableAgentAiIntegration(unittest.TestCase):
    """Integration test using real OpenAI API"""

    def test_plot_delegation_scatter_plot(self):
        """Test that TableAgentAi correctly delegates plot requests to PlotlyAgentAi"""
        # Create simple dataframe with two numeric columns
        test_dataframe = pd.DataFrame({"hello": [1, 2, 3, 4, 5], "y_values": [2, 4, 1, 8, 6]})

        # Create TableAgentAi instance
        agent = TableAgentAi(
            openai_api_key=os.getenv("OPENAI_API_KEY", ""),
            table=Table(test_dataframe),
            model="gpt-4o",  # Use cheaper model for testing
            temperature=0.1,
            table_unique_name="test_data",
        )

        # Request plot generation - should trigger plot delegation
        # user_query = "Create a scatter plot showing the relationship between x_values and y_values"
        user_query = "Can you rename the column 'hello' to 'x_values', then make a scatter plot with column x_values as x and column y_values as y"

        events = list(agent.call_agent(user_query))

        transform_events = [e for e in events if isinstance(e, TableTransformEvent)]
        self.assertEqual(len(transform_events), 1)

        # Check the plot
        plot_events = [e for e in events if isinstance(e, PlotGeneratedEvent)]
        self.assertEqual(len(plot_events), 1)

    def test_transform_delegation_add_column(self):
        """Test that TableAgentAi correctly delegates transform requests to TableTransformAgentAi"""
        # Create simple dataframe with two numeric columns
        test_dataframe = pd.DataFrame({"hello": [1, 2, 3, 4, 5], "y_values": [2, 4, 1, 8, 6]})

        # Create TableAgentAi instance
        agent = TableAgentAi(
            openai_api_key=os.getenv("OPENAI_API_KEY", ""),
            table=Table(test_dataframe),
            model="gpt-4o",  # Use cheaper model for testing
            temperature=0.1,
            table_unique_name="test_data",
        )

        events = list(agent.call_agent("Rename the column 'hello' to 'x_values'"))

        transform_events = [e for e in events if isinstance(e, TableTransformEvent)]
        self.assertEqual(len(transform_events), 1)

        # Check the dataframe output after first agent call
        transformed_df = transform_events[0].table.to_dataframe()

        expected_df = pd.DataFrame({"x_values": [1, 2, 3, 4, 5], "y_values": [2, 4, 1, 8, 6]})
        pd.testing.assert_frame_equal(transformed_df.reset_index(drop=True), expected_df)

        # Generate a plot
        events = list(agent.call_agent("Now make a scatter plot with column x_values as x and column y_values as y"))
        plot_events = [e for e in events if isinstance(e, PlotGeneratedEvent)]
        self.assertEqual(len(plot_events), 1)

        replay_agent = TableAgentAi(
            openai_api_key=os.getenv("OPENAI_API_KEY", ""),
            model="gpt-4o",
            temperature=0.1,
            table=Table(test_dataframe),  # Empty table, will be replaced by replayed events
            table_unique_name="test_data",
        )

        # Replay the previous events
        events_to_replay = agent.get_events_for_serialization()
        replayed_events = list(replay_agent.replay_events(events_to_replay))

        # Check that we have the same number of transform events
        replay_transform_events = [e for e in replayed_events if isinstance(e, TableTransformEvent)]
        self.assertEqual(len(replay_transform_events), 1)

        # Check we have the same output dataframe
        replayed_transformed_df = replay_transform_events[0].table.to_dataframe()
        pd.testing.assert_frame_equal(replayed_transformed_df.reset_index(drop=True), expected_df)

        # check the plot events
        replay_plot_events = [e for e in replayed_events if isinstance(e, PlotGeneratedEvent)]
        self.assertEqual(len(replay_plot_events), 1)

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

        # Create TableAgentAi instance with first table
        agent = TableAgentAi(
            openai_api_key=os.getenv("OPENAI_API_KEY", ""),
            table=Table(sales_df),
            model="gpt-4o",
            temperature=0.1,
            table_unique_name="sales_data",
        )

        # Add second table
        agent.add_table("inventory_data", Table(inventory_df))

        # Request both operations in a single call
        events = list(
            agent.call_agent(
                "Filter the sales_data table to only include products with sales greater than 150 "
                "and name it 'high_sales_data'. Also filter the inventory_data table to only include "
                "products with stock less than 50 and name it 'low_stock_data'."
            )
        )

        # The agent should perform BOTH operations
        transform_events = [e for e in events if isinstance(e, TableTransformEvent)]
        self.assertEqual(len(transform_events), 2, "Should have TWO transform events (both operations)")

        # Verify both tables were created
        self.assertIn("high_sales_data", agent._tables, "high_sales_data should be created")
        self.assertIn("low_stock_data", agent._tables, "low_stock_data should be created")

        # Verify the first transformation was correct
        high_sales_table = agent._tables["high_sales_data"]
        high_sales_df = high_sales_table.get_data()
        self.assertTrue(all(high_sales_df["sales"] > 150), "All sales should be > 150")
        self.assertEqual(len(high_sales_df), 3, "Should have 3 products with sales > 150")

        # Verify the second transformation was correct
        low_stock_table = agent._tables["low_stock_data"]
        low_stock_df = low_stock_table.get_data()
        self.assertTrue(all(low_stock_df["stock"] < 50), "All stock should be < 50")
        self.assertEqual(len(low_stock_df), 2, "Should have 2 products with stock < 50")

        # Verify all tables exist
        expected_tables = ["sales_data", "inventory_data", "high_sales_data", "low_stock_data"]
        for table_name in expected_tables:
            self.assertIn(table_name, agent._tables, f"{table_name} should be in tables dict")

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

        # Create TableAgentAi instance with first table
        agent = TableAgentAi(
            openai_api_key=os.getenv("OPENAI_API_KEY", ""),
            table=Table(sales_df),
            model="gpt-4o",
            temperature=0.1,
            table_unique_name="sales_data",
        )

        # Add second table
        agent.add_table("inventory_data", Table(inventory_df))

        # Request a multi-table operation (merge)
        events = list(
            agent.call_agent(
                "Merge the sales_data and inventory_data tables on the 'product' column "
                "and name the result 'combined_data'."
            )
        )

        # The agent should perform a multi-table transformation
        multi_table_events = [e for e in events if isinstance(e, MultiTableTransformEvent)]
        self.assertEqual(len(multi_table_events), 1, "Should have ONE multi-table transform event")

        # Verify the merged table was created
        self.assertIn("combined_data", agent._tables, "combined_data should be created")

        # Verify the merged table has the expected structure
        combined_table = agent._tables["combined_data"]
        combined_df = combined_table.get_data()

        # Should have columns from both tables
        expected_columns = ["product", "sales", "region", "stock", "warehouse"]
        for col in expected_columns:
            self.assertIn(col, combined_df.columns, f"Column {col} should be in combined table")

        # Should have 5 rows (all products matched)
        self.assertEqual(len(combined_df), 5, "Should have 5 rows after merge")

        # Verify all original tables still exist
        expected_tables = ["sales_data", "inventory_data", "combined_data"]
        for table_name in expected_tables:
            self.assertIn(table_name, agent._tables, f"{table_name} should be in tables dict")
