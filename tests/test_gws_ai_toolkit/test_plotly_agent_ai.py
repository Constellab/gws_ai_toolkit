
import os
import unittest
from unittest.mock import MagicMock, patch

import pandas as pd
import plotly.graph_objects as go
from openai import OpenAI

from gws_ai_toolkit.core.agents.plotly_agent_ai import PlotlyAgentAi
from gws_ai_toolkit.core.agents.plotly_agent_ai_events import (
    ErrorEvent, PlotGeneratedEvent)


# test_plotly_agent_ai.py
class TestPlotyAgentAiIntegration(unittest.TestCase):
    """Integration test using real OpenAI API"""

    def test_real_plot_generation_scatter_plot(self):
        """Test real plot generation with OpenAI API for scatter plot"""
        # Create simple dataframe with two numeric columns
        test_dataframe = pd.DataFrame({
            'x_values': [1, 2, 3, 4, 5, 6, 7, 8, 9, 10],
            'y_values': [2, 4, 1, 8, 6, 9, 3, 7, 5, 10]
        })

        # Create Open*AI client using environment variable
        openai_client = OpenAI(api_key=os.getenv('OPENAI_API_KEY'))

        # Create PlotyAgentAi instance
        agent = PlotlyAgentAi(
            openai_client=openai_client,
            dataframe=test_dataframe,
            model="gpt-4o",  # Use cheaper model for testing
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
        self.assertEqual(len(plot_events), 1)

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

        # Check that discussion continuation is working by generating another plot
        user_query2 = "Change the color of the markers to red"

        events2 = list(agent.generate_plot_stream(user_query2))
        plot_events2 = [e for e in events2 if isinstance(e, PlotGeneratedEvent)]
        self.assertGreater(len(plot_events2), 0)
        plot_event2 = plot_events2[0]
        self.assertIsInstance(plot_event2.figure, go.Figure)
        figure2 = plot_event2.figure
        self.assertGreater(len(figure2.data), 0)
        self.assertEqual(figure2.data[0].marker.color, 'red')

    @patch.object(PlotlyAgentAi, '_get_code_execution_globals')
    def test_real_plot_generation_with_error(self, mock_get_globals):
        """
        Test real plot generation with OpenAI API for scatter plot
        This first generation will fail due to missing 'go' in globals
        and the agent should recover and produce a valid plot.

        """
        # Create simple dataframe with two numeric columns

        mock_globals = {
            'pd': pd,
            # 'go': go, # remove the go to have an error
            '__builtins__': __builtins__
        }
        mock_get_globals.return_value = mock_globals

        test_dataframe = pd.DataFrame({
            'x_values': [1, 2, 3, 4, 5, 6, 7, 8, 9, 10],
            'y_values': [2, 4, 1, 8, 6, 9, 3, 7, 5, 10]
        })

        # Create Open*AI client using environment variable
        openai_client = OpenAI(api_key=os.getenv('OPENAI_API_KEY'))

        # Create PlotyAgentAi instance
        agent = PlotlyAgentAi(
            openai_client=openai_client,
            dataframe=test_dataframe,
            model="gpt-4o",  # Use cheaper model for testing
            temperature=0.1
        )

        # Request scatter plot generation
        user_query = "Create a scatter plot with x_values as x-axis and y_values as y-axis"

        # Collect all events from the stream
        events = list(agent.generate_plot_stream(user_query))

        # Verify we received events
        self.assertGreater(len(events), 0)

        error_events = [e for e in events if isinstance(e, ErrorEvent)]
        self.assertEqual(len(error_events), 1)
        self.assertIn("name 'go' is not defined", error_events[0].message)

        # Look for PlotGeneratedEvent
        plot_events = [e for e in events if isinstance(e, PlotGeneratedEvent)]

        # Should have at least one plot generated event
        self.assertEqual(len(plot_events), 1)

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
