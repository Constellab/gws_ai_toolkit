import unittest

import pandas as pd
import plotly.graph_objects as go
from gws_ai_toolkit.core.agents.agent_events import CodeEvent, FunctionErrorEvent
from gws_ai_toolkit.core.agents.table.plotly_agent_ai import PlotlyAgentAi
from gws_ai_toolkit.core.agents.table.plotly_agent_ai_events import PlotGeneratedEvent
from gws_ai_toolkit.core.agents.table.table_agent_event_base import UserQueryTableEvent
from gws_core import Table

from .agent_test_helper import PLOTLY, ScriptedModel, ToolCall

SCATTER_CODE = (
    "fig = go.Figure()\n"
    "fig.add_trace(go.Scatter(x=df['x_values'], y=df['y_values'], mode='markers'))"
)


# test_plotly_agent_ai.py
class TestPlotlyAgentAi(unittest.TestCase):
    """Drives PlotlyAgentAi through a scripted model, so no API call is made."""

    def _dataframe(self) -> pd.DataFrame:
        """Build the test dataframe.

        Returns:
            A two-column numeric dataframe.
        """
        return pd.DataFrame(
            {
                "x_values": [1, 2, 3, 4, 5, 6, 7, 8, 9, 10],
                "y_values": [2, 4, 1, 8, 6, 9, 3, 7, 5, 10],
            }
        )

    def _build_agent(self, turns: list) -> PlotlyAgentAi:
        """Build a plot agent backed by a scripted model.

        Args:
            turns: The scripted turns for the plot agent.

        Returns:
            The agent.
        """
        scripted = ScriptedModel(script={PLOTLY: turns})
        return PlotlyAgentAi(
            openai_api_key=None,
            model=scripted.build(),
            temperature=0.1,
        )

    def test_plot_generation_scatter_plot(self):
        """The agent runs the generated code and emits the resulting figure."""
        agent = self._build_agent(
            [
                ToolCall(
                    "generate_plotly_figure",
                    {"code": SCATTER_CODE, "plot_name": "X Values Versus Y Values"},
                ),
                "Here is your scatter plot.",
            ]
        )

        user_query = UserQueryTableEvent(
            query="Create a scatter plot with x_values as x-axis and y_values as y-axis",
            table=Table(self._dataframe()),
            agent_id=agent.id,
        )

        events = list(agent.call_agent(user_query))

        self.assertGreater(len(events), 0)

        plot_events = [e for e in events if isinstance(e, PlotGeneratedEvent)]
        self.assertEqual(len(plot_events), 1)

        plot_event = plot_events[0]
        figure = plot_event.plot.get_figure()
        self.assertIsInstance(figure, go.Figure)
        self.assertGreater(len(figure.data), 0)
        self.assertEqual(figure.data[0].type, "scatter")
        self.assertEqual(figure.data[0].mode, "markers")
        self.assertEqual(plot_event.plot.name, "X Values Versus Y Values")

        # The generated code is surfaced as its own event before the figure.
        code_events = [e for e in events if isinstance(e, CodeEvent)]
        self.assertEqual(len(code_events), 1)
        self.assertIn("go.Scatter", code_events[0].code)

    def test_plot_generation_recovers_from_a_code_error(self):
        """A first attempt whose code fails is reported, then the model corrects itself."""
        agent = self._build_agent(
            [
                # 'undefined_helper' does not exist in the execution globals.
                ToolCall(
                    "generate_plotly_figure",
                    {"code": "fig = undefined_helper()", "plot_name": "Broken Plot"},
                ),
                ToolCall(
                    "generate_plotly_figure",
                    {"code": SCATTER_CODE, "plot_name": "X Values Versus Y Values"},
                ),
                "Fixed, here is your scatter plot.",
            ]
        )

        user_query = UserQueryTableEvent(
            query="Create a scatter plot with x_values as x-axis and y_values as y-axis",
            table=Table(self._dataframe()),
            agent_id=agent.id,
        )

        events = list(agent.call_agent(user_query))

        error_events = [e for e in events if isinstance(e, FunctionErrorEvent)]
        self.assertEqual(len(error_events), 1)
        self.assertIn("undefined_helper", error_events[0].message)

        plot_events = [e for e in events if isinstance(e, PlotGeneratedEvent)]
        self.assertEqual(len(plot_events), 1)

        figure = plot_events[0].plot.get_figure()
        self.assertEqual(figure.data[0].type, "scatter")

    def test_missing_code_reports_an_error(self):
        """An empty code argument is reported rather than executed."""
        agent = self._build_agent(
            [
                ToolCall("generate_plotly_figure", {"code": "  ", "plot_name": "Empty"}),
                "I could not produce the plot.",
            ]
        )

        user_query = UserQueryTableEvent(
            query="Plot something",
            table=Table(self._dataframe()),
            agent_id=agent.id,
        )

        events = list(agent.call_agent(user_query))

        error_events = [e for e in events if isinstance(e, FunctionErrorEvent)]
        self.assertEqual(len(error_events), 1)
        self.assertIn("No code provided", error_events[0].message)

    def test_sub_agent_stops_after_a_successful_call(self):
        """With skip_success_response, the run ends on success instead of asking for a summary."""
        scripted = ScriptedModel(
            script={
                PLOTLY: [
                    ToolCall(
                        "generate_plotly_figure",
                        {"code": SCATTER_CODE, "plot_name": "X Values Versus Y Values"},
                    )
                ]
            }
        )
        agent = PlotlyAgentAi(
            openai_api_key=None,
            model=scripted.build(),
            temperature=0.1,
            skip_success_response=True,
        )

        user_query = UserQueryTableEvent(
            query="Plot it",
            table=Table(self._dataframe()),
            agent_id=agent.id,
        )

        events = list(agent.call_agent(user_query))

        self.assertEqual(len([e for e in events if isinstance(e, PlotGeneratedEvent)]), 1)
        # A single model turn: the script has no second turn, and none was requested.
        self.assertEqual(scripted.calls, [(PLOTLY, 0)])


if __name__ == "__main__":
    unittest.main()
