import os
import unittest
from unittest.mock import patch

import pandas as pd
from gws_ai_toolkit.core.agents.base_function_agent_events import FunctionErrorEvent
from gws_ai_toolkit.core.agents.table.table_agent_event_base import UserQueryTableTransformEvent
from gws_ai_toolkit.core.agents.table.table_transform_agent_ai import TableTransformAgentAi
from gws_ai_toolkit.core.agents.table.table_transform_agent_ai_events import TableTransformEvent
from gws_core import Table


# test_table_transform_agent_ai.py
class TestTableTransformAgentAiIntegration(unittest.TestCase):
    """Integration test using real OpenAI API"""

    def test_real_dataframe_transformation_add_column(self):
        """Test real DataFrame transformation with OpenAI API for adding a column"""
        # Create simple dataframe with numeric columns
        test_dataframe = pd.DataFrame(
            {
                "age": [25, 30, 35, 40, 45],
                "salary": [50000, 60000, 70000, 80000, 90000],
                "experience": [2, 5, 8, 12, 15],
            }
        )

        # Create TableTransformAgentAi instance without table
        agent = TableTransformAgentAi(
            openai_api_key=os.getenv("OPENAI_API_KEY", ""),
            model="gpt-4o",  # Use cheaper model for testing
            temperature=0.1,
        )

        # Create user query with table
        user_query = UserQueryTableTransformEvent(
            query="Add a new column called 'salary_per_year_exp' that calculates salary divided by experience",
            table=Table(test_dataframe),
            table_name="employee_data",
            output_table_name="employee_data_with_ratio",
            agent_id=agent.id,
        )

        # Collect all events from the stream
        events = list(agent.call_agent(user_query))

        # Verify we received events
        self.assertGreater(len(events), 0)

        # Look for DataFrameTransformEvent
        transform_events = [e for e in events if isinstance(e, TableTransformEvent)]

        # Should have at least one transform event
        self.assertEqual(len(transform_events), 1)

        # Verify the transformed DataFrame
        transform_event = transform_events[0]
        self.assertIsInstance(transform_event.table, Table)

        # Verify the new column was added
        transformed_df = transform_event.table.to_dataframe()
        self.assertIn("salary_per_year_exp", transformed_df.columns)

        # Verify the calculation is correct
        expected_values = test_dataframe["salary"] / test_dataframe["experience"]
        pd.testing.assert_series_equal(
            transformed_df["salary_per_year_exp"], expected_values, check_names=False
        )

        # Verify the generated code contains expected elements
        self.assertIn("salary_per_year_exp", transform_event.code)
        self.assertIn("salary", transform_event.code)
        self.assertIn("experience", transform_event.code)

        # Check that discussion continuation is working by making another transformation
        # Use the transformed table for the next query
        user_query2 = UserQueryTableTransformEvent(
            query="Filter the dataframe to keep only rows where age is greater than 30",
            table=transform_event.table,
            table_name="employee_data_with_ratio",
            output_table_name="filtered_employees",
            agent_id=agent.id,
        )

        events2 = list(agent.call_agent(user_query2))
        transform_events2 = [e for e in events2 if isinstance(e, TableTransformEvent)]
        self.assertGreater(len(transform_events2), 0)

        transform_event2 = transform_events2[0]
        self.assertIsInstance(transform_event2.table, Table)

        # Verify filtering worked
        transformed_df2 = transform_event2.table.to_dataframe()
        self.assertTrue(all(transformed_df2["age"] > 30))
        self.assertEqual(len(transformed_df2), 3)  # Should have 3 rows with age > 30

    @patch.object(TableTransformAgentAi, "_get_code_execution_globals")
    def test_real_transformation_with_error_recovery(self, mock_get_globals):
        """
        Test real DataFrame transformation with OpenAI API
        This first transformation will fail due to missing 'pd' in globals
        and the agent should recover and produce a valid transformation.
        """
        # Setup mock to cause initial error
        mock_globals = {
            # 'pd': pd,  # Remove pd to cause an error
            "__builtins__": __builtins__
        }
        mock_get_globals.return_value = mock_globals

        test_dataframe = pd.DataFrame({"name": ["Alice", "Bob", "Charlie"], "score": [85, 90, 75]})

        # Create TableTransformAgentAi instance without table
        agent = TableTransformAgentAi(
            openai_api_key=os.getenv("OPENAI_API_KEY", ""), model="gpt-4o", temperature=0.1
        )

        # Create user query with table
        user_query = UserQueryTableTransformEvent(
            query="Add a new column called 'grade_category' using pd.cut to categorize scores into 'Low' (0-80), 'Medium' (80-90), and 'High' (90-100)",
            table=Table(test_dataframe),
            table_name="student_scores",
            output_table_name="student_grades",
            agent_id=agent.id,
        )

        # Collect all events from the stream
        events = list(agent.call_agent(user_query))

        # Verify we received events
        self.assertGreater(len(events), 0)

        # Should have error events due to missing 'pd'
        error_events = [e for e in events if isinstance(e, FunctionErrorEvent)]
        self.assertEqual(len(error_events), 1)
        self.assertIn("name 'pd' is not defined", error_events[0].message)

        # Look for DataFrameTransformEvent (should still succeed after retry)
        transform_events = [e for e in events if isinstance(e, TableTransformEvent)]

        # Should have at least one transform event
        self.assertEqual(len(transform_events), 1)

        # Verify the transformed DataFrame
        transform_event = transform_events[0]
        self.assertIsInstance(transform_event.table, Table)

        # Verify the new column was added correctly
        transformed_df = transform_event.table.to_dataframe()
        self.assertIn("grade_category", transformed_df.columns)

        # Verify the categorization is correct
        self.assertEqual(
            transformed_df.loc[transformed_df["score"] == 75, "grade_category"].iloc[0], "Low"
        )
        self.assertEqual(
            transformed_df.loc[transformed_df["score"] == 85, "grade_category"].iloc[0], "Medium"
        )
        self.assertEqual(
            transformed_df.loc[transformed_df["score"] == 90, "grade_category"].iloc[0], "High"
        )
