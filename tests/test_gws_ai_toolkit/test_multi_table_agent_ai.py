import unittest

import pandas as pd
from gws_ai_toolkit.core.agents.base_function_agent_events import CodeEvent, FunctionErrorEvent
from gws_ai_toolkit.core.agents.table.multi_table_agent_ai import MultiTableAgentAi
from gws_ai_toolkit.core.agents.table.multi_table_agent_ai_events import MultiTableTransformEvent
from gws_ai_toolkit.core.agents.table.table_agent_event_base import UserQueryMultiTablesEvent
from gws_core import Table

from .agent_test_helper import MULTI_TABLE, ScriptedModel, ToolCall

MERGE_CODE = (
    "merged = pd.merge(tables['sales'], tables['products'], on='product_id')\n"
    "result_tables = {\n"
    "    'merged_sales': merged,\n"
    "    'sales_by_category': merged.groupby('category', as_index=False)['sales_amount'].sum(),\n"
    "}"
)


# test_multi_table_agent_ai.py
class TestMultiTableAgentAi(unittest.TestCase):
    """Drives MultiTableAgentAi through a scripted model, so no API call is made."""

    def _tables(self) -> dict[str, Table]:
        """Build the input tables.

        Returns:
            A sales table and a products table sharing a product_id column.
        """
        sales_data = pd.DataFrame(
            {
                "product_id": [1, 2, 3, 4, 5],
                "sales_amount": [100, 150, 200, 80, 120],
                "date": ["2023-01-01", "2023-01-02", "2023-01-03", "2023-01-04", "2023-01-05"],
            }
        )
        product_data = pd.DataFrame(
            {
                "product_id": [1, 2, 3, 4, 5],
                "product_name": ["Widget A", "Widget B", "Widget C", "Widget D", "Widget E"],
                "category": ["Electronics", "Electronics", "Clothing", "Electronics", "Clothing"],
            }
        )
        return {"sales": Table(sales_data), "products": Table(product_data)}

    def _build_agent(self, turns: list) -> MultiTableAgentAi:
        """Build a multi-table agent backed by a scripted model.

        Args:
            turns: The scripted turns for the multi-table agent.

        Returns:
            The agent.
        """
        scripted = ScriptedModel(script={MULTI_TABLE: turns})
        return MultiTableAgentAi(
            openai_api_key=None,
            model=scripted.build(),
            temperature=0.1,
        )

    def test_multi_table_transformation_merge(self):
        """The agent merges the tables and returns every table its code produced."""
        agent = self._build_agent(
            [
                ToolCall("transform_multiple_tables", {"code": MERGE_CODE}),
                "Merged the tables and summarised sales by category.",
            ]
        )

        user_query = UserQueryMultiTablesEvent(
            query=(
                "Merge the sales and products tables on product_id and create a summary table "
                "showing total sales by category"
            ),
            tables=self._tables(),
            agent_id=agent.id,
        )

        events = list(agent.call_agent(user_query))

        self.assertGreater(len(events), 0)

        transform_events = [e for e in events if isinstance(e, MultiTableTransformEvent)]
        self.assertEqual(len(transform_events), 1)

        result_tables = transform_events[0].tables
        self.assertIsInstance(result_tables, dict)
        self.assertEqual(set(result_tables), {"merged_sales", "sales_by_category"})

        summary_df = result_tables["sales_by_category"].get_data()
        self.assertIn("category", summary_df.columns)
        categories = summary_df["category"].tolist()
        self.assertIn("Electronics", categories)
        self.assertIn("Clothing", categories)

        # Electronics: 100 + 150 + 80, Clothing: 200 + 120
        totals = dict(zip(summary_df["category"], summary_df["sales_amount"], strict=True))
        self.assertEqual(totals["Electronics"], 330)
        self.assertEqual(totals["Clothing"], 320)

        code_events = [e for e in events if isinstance(e, CodeEvent)]
        self.assertEqual(len(code_events), 1)
        self.assertIn("merge", code_events[0].code.lower())

    def test_code_not_returning_result_tables_reports_an_error(self):
        """Code that does not define result_tables is reported to the user."""
        agent = self._build_agent(
            [
                ToolCall(
                    "transform_multiple_tables",
                    {"code": "merged = pd.merge(tables['sales'], tables['products'], on='product_id')"},
                ),
                "I could not produce the tables.",
            ]
        )

        user_query = UserQueryMultiTablesEvent(
            query="Merge the tables",
            tables=self._tables(),
            agent_id=agent.id,
        )

        events = list(agent.call_agent(user_query))

        error_events = [e for e in events if isinstance(e, FunctionErrorEvent)]
        self.assertEqual(len(error_events), 1)
        self.assertIn("result_tables", error_events[0].message)

    def test_expected_output_table_names_are_passed_to_the_model(self):
        """Requested output table names reach the instructions the model is given."""
        agent = self._build_agent(
            [
                ToolCall(
                    "transform_multiple_tables",
                    {
                        "code": (
                            "result_tables = {'combined': pd.merge("
                            "tables['sales'], tables['products'], on='product_id')}"
                        )
                    },
                ),
                "Done.",
            ]
        )

        user_query = UserQueryMultiTablesEvent(
            query="Merge the tables into combined",
            tables=self._tables(),
            agent_id=agent.id,
            output_table_names=["combined"],
        )

        instructions = agent._get_ai_instruction(user_query)
        self.assertIn("'combined'", instructions)

        events = list(agent.call_agent(user_query))
        transform_events = [e for e in events if isinstance(e, MultiTableTransformEvent)]
        self.assertEqual(set(transform_events[0].tables), {"combined"})


if __name__ == "__main__":
    unittest.main()
