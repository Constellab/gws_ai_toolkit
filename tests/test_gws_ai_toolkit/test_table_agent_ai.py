import os
import unittest

import pandas as pd
from gws_core import Table
from openai import OpenAI

from gws_ai_toolkit.core.agents.base_function_agent_events import \
    TextDeltaEvent
from gws_ai_toolkit.core.agents.plotly_agent_ai_events import \
    PlotGeneratedEvent
from gws_ai_toolkit.core.agents.table_agent_ai import TableAgentAi
from gws_ai_toolkit.core.agents.table_transform_agent_ai_events import \
    TableTransformEvent


# test_table_agent_ai
class TestTableAgentAiIntegration(unittest.TestCase):
    """Integration test using real OpenAI API"""

    def test_plot_delegation_scatter_plot(self):
        """Test that TableAgentAi correctly delegates plot requests to PlotlyAgentAi"""
        # Create simple dataframe with two numeric columns
        test_dataframe = pd.DataFrame({
            'x_values': [1, 2, 3, 4, 5],
            'y_values': [2, 4, 1, 8, 6]
        })

        # Create OpenAI client using environment variable
        openai_client = OpenAI(api_key=os.getenv('OPENAI_API_KEY'))

        # Create TableAgentAi instance
        agent = TableAgentAi(
            openai_client=openai_client,
            table=Table(test_dataframe),
            model="gpt-4o",  # Use cheaper model for testing
            temperature=0.1,
            table_name="test_data"
        )

        # Request plot generation - should trigger plot delegation
        # user_query = "Create a scatter plot showing the relationship between x_values and y_values"
        user_query = "Can you multiply all column by 10, then make a scatter plot with column x_values as x and column y_values as y"

        events = list(agent.call_agent(user_query))

        transform_events = [e for e in events if isinstance(e, TableTransformEvent)]
        self.assertEqual(len(transform_events), 1)

        # Check the plot
        plot_events = [e for e in events if isinstance(e, PlotGeneratedEvent)]
        self.assertEqual(len(plot_events), 1)

    def test_transform_delegation_add_column(self):
        """Test that TableAgentAi correctly delegates transform requests to TableTransformAgentAi"""
        # Create simple dataframe
        # Create simple dataframe with two numeric columns
        test_dataframe = pd.DataFrame({
            'x_values': [1, 2, 3, 4, 5],
            'y_values': [2, 4, 1, 8, 6]
        })

        # Create OpenAI client using environment variable
        openai_client = OpenAI(api_key=os.getenv('OPENAI_API_KEY'))

        # Create TableAgentAi instance
        agent = TableAgentAi(
            openai_client=openai_client,
            table=Table(test_dataframe),
            model="gpt-4o",  # Use cheaper model for testing
            temperature=0.1,
            table_name="test_data"
        )

        events = list(agent.call_agent("Can you multiply all column by 10"))

        transform_events = [e for e in events if isinstance(e, TableTransformEvent)]
        self.assertEqual(len(transform_events), 1)

        # Generate a plot
        events = list(agent.call_agent("Now make a scatter plot with column x_values as x and column y_values as y"))
        plot_events = [e for e in events if isinstance(e, PlotGeneratedEvent)]
        self.assertEqual(len(plot_events), 1)
