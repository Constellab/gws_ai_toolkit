import unittest

import pandas as pd
from gws_ai_toolkit.core.agents.agent_events import (
    CodeEvent,
    ErrorEvent,
    FunctionErrorEvent,
)
from gws_ai_toolkit.core.agents.table.table_agent_event_base import UserQueryTableTransformEvent
from gws_ai_toolkit.core.agents.table.table_transform_agent_ai import TableTransformAgentAi
from gws_ai_toolkit.core.agents.table.table_transform_agent_ai_events import TableTransformEvent
from gws_core import Table

from .agent_test_helper import TRANSFORM, ScriptedModel, ToolCall

RATIO_CODE = (
    "transformed_df = df.copy()\n"
    "transformed_df['salary_per_year_exp'] = df['salary'] / df['experience']"
)
FILTER_CODE = "transformed_df = df[df['age'] > 30]"
# right=False so a score of exactly 90 lands in the 'High' band, as the request describes.
GRADE_CODE = (
    "transformed_df = df.copy()\n"
    "transformed_df['grade_category'] = pd.cut(df['score'], bins=[0, 80, 90, 101], "
    "labels=['Low', 'Medium', 'High'], right=False)"
)


# test_table_transform_agent_ai.py
class TestTableTransformAgentAi(unittest.TestCase):
    """Drives TableTransformAgentAi through a scripted model, so no API call is made."""

    def _employee_dataframe(self) -> pd.DataFrame:
        """Build the employee test dataframe.

        Returns:
            A dataframe with age, salary and experience columns.
        """
        return pd.DataFrame(
            {
                "age": [25, 30, 35, 40, 45],
                "salary": [50000, 60000, 70000, 80000, 90000],
                "experience": [2, 5, 8, 12, 15],
            }
        )

    def _build_agent(self, turns: list) -> tuple[TableTransformAgentAi, ScriptedModel]:
        """Build a transform agent backed by a scripted model.

        Args:
            turns: The scripted turns for the transform agent.

        Returns:
            Tuple of (agent, scripted model).
        """
        scripted = ScriptedModel(script={TRANSFORM: turns})
        agent = TableTransformAgentAi(
            openai_api_key=None,
            model=scripted.build(),
            temperature=0.1,
        )
        return agent, scripted

    def test_dataframe_transformation_add_column(self):
        """Two successive transformations run on one agent, continuing its conversation."""
        test_dataframe = self._employee_dataframe()

        agent, scripted = self._build_agent(
            [
                ToolCall(
                    "transform_dataframe",
                    {"code": RATIO_CODE, "transformed_table_name": "employee_data_with_ratio"},
                ),
                "Added the ratio column.",
                ToolCall(
                    "transform_dataframe",
                    {"code": FILTER_CODE, "transformed_table_name": "filtered_employees"},
                ),
                "Filtered the rows.",
            ]
        )

        user_query = UserQueryTableTransformEvent(
            query=(
                "Add a new column called 'salary_per_year_exp' that calculates salary divided "
                "by experience"
            ),
            table=Table(test_dataframe),
            table_name="employee_data",
            output_table_name="employee_data_with_ratio",
            agent_id=agent.id,
        )

        events = list(agent.call_agent(user_query))

        self.assertGreater(len(events), 0)

        transform_events = [e for e in events if isinstance(e, TableTransformEvent)]
        self.assertEqual(len(transform_events), 1)

        transform_event = transform_events[0]
        self.assertIsInstance(transform_event.table, Table)
        self.assertEqual(transform_event.table_name, "employee_data_with_ratio")

        transformed_df = transform_event.table.to_dataframe()
        self.assertIn("salary_per_year_exp", transformed_df.columns)

        expected_values = test_dataframe["salary"] / test_dataframe["experience"]
        pd.testing.assert_series_equal(
            transformed_df["salary_per_year_exp"], expected_values, check_names=False
        )

        self.assertIn("salary_per_year_exp", transform_event.code)

        # Second turn on the same agent: only reachable because the conversation history is
        # carried on the instance.
        user_query2 = UserQueryTableTransformEvent(
            query="Filter the dataframe to keep only rows where age is greater than 30",
            table=transform_event.table,
            table_name="employee_data_with_ratio",
            output_table_name="filtered_employees",
            agent_id=agent.id,
        )

        events2 = list(agent.call_agent(user_query2))
        transform_events2 = [e for e in events2 if isinstance(e, TableTransformEvent)]
        self.assertEqual(len(transform_events2), 1)

        transformed_df2 = transform_events2[0].table.to_dataframe()
        self.assertTrue(all(transformed_df2["age"] > 30))
        self.assertEqual(len(transformed_df2), 3)

        self.assertEqual([turn for _, turn in scripted.calls], [0, 1, 2, 3])

    def test_transformation_with_error_recovery(self):
        """A first attempt failing on a missing global is reported, then the retry succeeds.

        The execution globals are trimmed so the first attempt raises, which is what drives the
        retry: the agent reports the failure and asks the model to fix its code.
        """
        test_dataframe = pd.DataFrame({"name": ["Alice", "Bob", "Charlie"], "score": [85, 90, 75]})

        agent, _ = self._build_agent(
            [
                # References `pd`, which the first attempt's globals will not have.
                ToolCall(
                    "transform_dataframe",
                    {"code": GRADE_CODE, "transformed_table_name": "student_grades"},
                ),
                ToolCall(
                    "transform_dataframe",
                    {"code": GRADE_CODE, "transformed_table_name": "student_grades"},
                ),
                "Fixed and categorised the scores.",
            ]
        )

        # The first attempt runs without 'pd' in its globals and therefore fails; every
        # later attempt gets the real globals and can succeed.
        real_globals = agent._get_code_execution_globals
        attempts: list[int] = []

        def globals_missing_pd_on_first_attempt() -> dict:
            attempts.append(1)
            if len(attempts) == 1:
                return {"__builtins__": __builtins__}
            return real_globals()

        agent._get_code_execution_globals = globals_missing_pd_on_first_attempt  # type: ignore[method-assign]

        user_query = UserQueryTableTransformEvent(
            query=(
                "Add a new column called 'grade_category' using pd.cut to categorize scores "
                "into 'Low' (0-80), 'Medium' (80-90), and 'High' (90-100)"
            ),
            table=Table(test_dataframe),
            table_name="student_scores",
            output_table_name="student_grades",
            agent_id=agent.id,
        )

        events = list(agent.call_agent(user_query))

        self.assertGreater(len(events), 0)

        error_events = [e for e in events if isinstance(e, FunctionErrorEvent)]
        self.assertEqual(len(error_events), 1)
        self.assertIn("name 'pd' is not defined", error_events[0].message)

        transform_events = [e for e in events if isinstance(e, TableTransformEvent)]
        self.assertEqual(len(transform_events), 1)

        transformed_df = transform_events[0].table.to_dataframe()
        self.assertIn("grade_category", transformed_df.columns)

        self.assertEqual(
            transformed_df.loc[transformed_df["score"] == 75, "grade_category"].iloc[0], "Low"
        )
        self.assertEqual(
            transformed_df.loc[transformed_df["score"] == 85, "grade_category"].iloc[0], "Medium"
        )
        self.assertEqual(
            transformed_df.loc[transformed_df["score"] == 90, "grade_category"].iloc[0], "High"
        )

    def test_code_not_defining_transformed_df_reports_an_error(self):
        """Code that does not define transformed_df is reported to the user."""
        agent, _ = self._build_agent(
            [
                ToolCall(
                    "transform_dataframe",
                    {"code": "other_name = df.copy()", "transformed_table_name": "out"},
                ),
                "I could not produce the table.",
            ]
        )

        user_query = UserQueryTableTransformEvent(
            query="Copy the dataframe",
            table=Table(self._employee_dataframe()),
            table_name="employee_data",
            output_table_name="out",
            agent_id=agent.id,
        )

        events = list(agent.call_agent(user_query))

        error_events = [e for e in events if isinstance(e, FunctionErrorEvent)]
        self.assertEqual(len(error_events), 1)
        self.assertIn("transformed_df", error_events[0].message)

    def test_repeated_failures_stop_with_an_error(self):
        """Once the retry budget is exhausted the run reports a terminal error."""
        failing_call = ToolCall(
            "transform_dataframe",
            {"code": "transformed_df = undefined_name", "transformed_table_name": "out"},
        )
        # One more scripted turn than the retry budget, so the budget is what stops the run.
        agent, _ = self._build_agent(
            [failing_call] * (TableTransformAgentAi.MAX_CONSECUTIVE_ERRORS + 2)
        )

        user_query = UserQueryTableTransformEvent(
            query="Do something impossible",
            table=Table(self._employee_dataframe()),
            table_name="employee_data",
            output_table_name="out",
            agent_id=agent.id,
        )

        events = list(agent.call_agent(user_query))

        error_events = [e for e in events if isinstance(e, ErrorEvent)]
        self.assertEqual(len(error_events), 1)
        self.assertIn("Maximum consecutive", error_events[0].message)

        self.assertEqual(len([e for e in events if isinstance(e, TableTransformEvent)]), 0)
        # Every attempt surfaced its own failure to the user.
        self.assertGreaterEqual(len([e for e in events if isinstance(e, CodeEvent)]), 2)


if __name__ == "__main__":
    unittest.main()
