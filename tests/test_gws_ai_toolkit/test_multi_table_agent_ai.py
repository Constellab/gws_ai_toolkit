import os
import unittest

import pandas as pd
from gws_core import Table
from openai import OpenAI

from gws_ai_toolkit.core.agents.multi_table_agent_ai import MultiTableAgentAi
from gws_ai_toolkit.core.agents.multi_table_agent_ai_events import \
    MultiTableTransformEvent


# test_multi_table_agent_ai.py
class TestMultiTableAgentAiIntegration(unittest.TestCase):
    """Integration test using real OpenAI API"""

    def test_real_multi_table_transformation_merge(self):
        """Test real multi-table transformation with OpenAI API for merging tables"""
        # Create test tables
        sales_data = pd.DataFrame({
            'product_id': [1, 2, 3, 4, 5],
            'sales_amount': [100, 150, 200, 80, 120],
            'date': ['2023-01-01', '2023-01-02', '2023-01-03', '2023-01-04', '2023-01-05']
        })

        product_data = pd.DataFrame({
            'product_id': [1, 2, 3, 4, 5],
            'product_name': ['Widget A', 'Widget B', 'Widget C', 'Widget D', 'Widget E'],
            'category': ['Electronics', 'Electronics', 'Clothing', 'Electronics', 'Clothing']
        })

        tables = {
            'sales': Table(sales_data),
            'products': Table(product_data)
        }

        # Create OpenAI client using environment variable
        openai_client = OpenAI(api_key=os.getenv('OPENAI_API_KEY'))

        # Create MultiTableAgentAi instance
        agent = MultiTableAgentAi(
            openai_client=openai_client,
            tables=tables,
            model="gpt-4o",  # Use cheaper model for testing
            temperature=0.1
        )

        # Request transformation to merge tables and create summary
        user_query = "Merge the sales and products tables on product_id and create a summary table showing total sales by category"

        # Collect all events from the stream
        events = list(agent.call_agent(user_query))

        # Verify we received events
        self.assertGreater(len(events), 0)

        # Look for MultiTableTransformEvent
        transform_events = [e for e in events if isinstance(e, MultiTableTransformEvent)]

        # Should have at least one transform event
        self.assertEqual(len(transform_events), 1)

        # Verify the transformed tables
        transform_event = transform_events[0]
        self.assertIsInstance(transform_event.tables, dict)
        self.assertGreater(len(transform_event.tables), 0)

        # Verify we have meaningful results
        result_tables = transform_event.tables

        # Should have at least one result table
        self.assertGreater(len(result_tables), 0)

        # Check that at least one table has the expected structure for category summary
        found_category_summary = False
        for table_name, table in result_tables.items():
            df = table.get_data()
            if 'category' in df.columns and any('sales' in col.lower() for col in df.columns):
                found_category_summary = True
                # Verify we have Electronics and Clothing categories
                categories = df['category'].tolist()
                self.assertIn('Electronics', categories)
                self.assertIn('Clothing', categories)
                break

        self.assertTrue(found_category_summary, "Should have a table with category and sales information")

        # Verify the generated code contains expected elements
        self.assertIn('merge', transform_event.code.lower())
        self.assertIn('product_id', transform_event.code)
        self.assertIn('groupby', transform_event.code.lower())
        self.assertIn('category', transform_event.code)


if __name__ == '__main__':
    unittest.main()
