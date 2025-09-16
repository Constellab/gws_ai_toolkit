
import os
import unittest

import pandas as pd
import plotly.graph_objects as go
from openai import OpenAI

from gws_ai_toolkit.core.agents.plotly_agent_ai import PlotyAgentAi
from gws_ai_toolkit.core.agents.plotly_agent_ai_events import \
    PlotGeneratedEvent


# test_plotly_agent_ai.py
class TestPlotyAgentAiIntegration(unittest.TestCase):
    """Integration test using real OpenAI API"""

    def test_real_plot_generation_scatter_plot(self):
        """Test real plot generation with OpenAI API for scatter plot"""
        print('Hello claude code')
        # Create simple dataframe with two numeric columns
        test_dataframe = pd.DataFrame({
            'x_values': [1, 2, 3, 4, 5, 6, 7, 8, 9, 10],
            'y_values': [2, 4, 1, 8, 6, 9, 3, 7, 5, 10]
        })

        # Create OpenAI client using environment variable
        openai_client = OpenAI(api_key=os.getenv('OPENAI_API_KEY'))

        # Create PlotyAgentAi instance
        agent = PlotyAgentAi(
            openai_client=openai_client,
            dataframe=test_dataframe,
            model="gpt-4o-mini",  # Use cheaper model for testing
            temperature=0.1
        )

        # Request scatter plot generation
        user_query = "Create a scatter plot with x_values as x-axis and y_values as y-axis"

        # Collect all events from the stream
        events = list(agent.generate_plot_stream(user_query))

        # Verify we received events
        self.assertGreater(len(events), 0)

        # Look for PlotGeneratedEvent
        plot_events = [e for e in events if isinstance(e, PlotGeneratedEvent)]

        # Should have at least one plot generated event
        self.assertGreater(len(plot_events), 0)

        # Verify the plot
        plot_event = plot_events[0]
        self.assertIsInstance(plot_event.figure, go.Figure)

        # Verify the figure has data and is a scatter plot
        figure = plot_event.figure
        self.assertGreater(len(figure.data), 0)
        self.assertEqual(figure.data[0].type, 'scatter')
        self.assertEqual(figure.data[0].mode, 'markers')

        # Verify the generated code contains expected elements
        self.assertIn('go.Scatter', plot_event.code)
        self.assertIn('x_values', plot_event.code)
        self.assertIn('y_values', plot_event.code)
