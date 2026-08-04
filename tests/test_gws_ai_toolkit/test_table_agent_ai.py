import asyncio
from typing import cast

import pandas as pd
from gws_ai_toolkit.core.agents.base_function_agent_events import (
    CreateSubAgent,
    FunctionCallEvent,
    ResponseCompletedEvent,
    ResponseCreatedEvent,
    ResponseFullTextEvent,
    SubAgentSuccess,
    TextDeltaEvent,
)
from gws_ai_toolkit.core.agents.table.multi_table_agent_ai_events import MultiTableTransformEvent
from gws_ai_toolkit.core.agents.table.plotly_agent_ai_events import PlotGeneratedEvent
from gws_ai_toolkit.core.agents.table.table_agent_ai import TableAgentAi
from gws_ai_toolkit.core.agents.table.table_agent_ai_events import UserQueryMultiTablesEvent
from gws_ai_toolkit.core.agents.table.table_agent_ai_service import TableAgentAiService
from gws_ai_toolkit.core.agents.table.table_transform_agent_ai_events import TableTransformEvent
from gws_core import BaseTestCase, ResourceSet, Table

from .agent_test_helper import (
    MULTI_TABLE,
    ORCHESTRATOR,
    PLOTLY,
    TRANSFORM,
    ScriptedModel,
    ToolCall,
)

RENAME_CODE = "transformed_df = df.rename(columns={'hello': 'x_values'})"
SCATTER_CODE = (
    "fig = go.Figure()\n"
    "fig.add_trace(go.Scatter(x=df['x_values'], y=df['y_values'], mode='markers'))"
)
# Within a single turn the orchestrator can only plot the tables it was handed, so a plot
# requested alongside a rename still sees the original column names.
SCATTER_CODE_ORIGINAL_COLUMNS = (
    "fig = go.Figure()\n"
    "fig.add_trace(go.Scatter(x=df['hello'], y=df['y_values'], mode='markers'))"
)


# test_table_agent_ai
class TestTableAgentAi(BaseTestCase):
    """Drives TableAgentAi through a scripted model, so no API call is made."""

    def _build_agent(self, script: dict) -> tuple[TableAgentAi, ScriptedModel]:
        """Build an agent backed by a scripted model.

        Args:
            script: Turns to replay per agent kind.

        Returns:
            Tuple of (agent, scripted model).
        """
        scripted = ScriptedModel(script=script)
        agent = TableAgentAi(
            openai_api_key=None,
            model=scripted.build(),
            temperature=0.1,
        )
        return agent, scripted

    def test_plot_delegation_scatter_plot(self):
        """TableAgentAi delegates a transform then a plot, each to its own sub-agent."""
        test_dataframe = pd.DataFrame({"hello": [1, 2, 3, 4, 5], "y_values": [2, 4, 1, 8, 6]})
        expected_df = pd.DataFrame({"x_values": [1, 2, 3, 4, 5], "y_values": [2, 4, 1, 8, 6]})

        agent, _ = self._build_agent(
            {
                ORCHESTRATOR: [
                    ToolCall(
                        "transform_table",
                        {
                            "table_name": "test_data",
                            "output_table_name": "renamed_data",
                            "user_request": "Rename 'hello' to 'x_values'",
                        },
                    ),
                    ToolCall(
                        "generate_plot",
                        {
                            "table_name": "test_data",
                            "user_request": "Scatter plot of the two columns",
                        },
                    ),
                    "Renamed the column and plotted it.",
                ],
                TRANSFORM: [
                    ToolCall(
                        "transform_dataframe",
                        {"code": RENAME_CODE, "transformed_table_name": "renamed_data"},
                    )
                ],
                PLOTLY: [
                    ToolCall(
                        "generate_plotly_figure",
                        {
                            "code": SCATTER_CODE_ORIGINAL_COLUMNS,
                            "plot_name": "Hello Versus Y Values",
                        },
                    )
                ],
            }
        )

        tables = {"test_data": Table(test_dataframe)}
        user_query = UserQueryMultiTablesEvent(
            query=(
                "Can you rename the column 'hello' to 'x_values', then make a scatter plot "
                "with column x_values as x and column y_values as y"
            ),
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
        """A second call_agent continues the conversation from client-side history."""
        test_dataframe = pd.DataFrame({"hello": [1, 2, 3, 4, 5], "y_values": [2, 4, 1, 8, 6]})
        expected_df = pd.DataFrame({"x_values": [1, 2, 3, 4, 5], "y_values": [2, 4, 1, 8, 6]})

        agent, scripted = self._build_agent(
            {
                ORCHESTRATOR: [
                    ToolCall(
                        "transform_table",
                        {
                            "table_name": "test_data",
                            "output_table_name": "renamed_data",
                            "user_request": "Rename 'hello' to 'x_values'",
                        },
                    ),
                    "Renamed the column.",
                    ToolCall(
                        "generate_plot",
                        {
                            "table_name": "renamed_data",
                            "user_request": "Scatter plot of x_values vs y_values",
                        },
                    ),
                    "Here is the plot.",
                ],
                TRANSFORM: [
                    ToolCall(
                        "transform_dataframe",
                        {"code": RENAME_CODE, "transformed_table_name": "renamed_data"},
                    )
                ],
                PLOTLY: [
                    ToolCall(
                        "generate_plotly_figure",
                        {"code": SCATTER_CODE, "plot_name": "X Values Versus Y Values"},
                    )
                ],
            }
        )

        tables = {"test_data": Table(test_dataframe)}
        user_query = UserQueryMultiTablesEvent(
            query="Rename the column 'hello' to 'x_values'",
            tables=tables,
            agent_id=agent.id,
        )

        events = list(agent.call_agent(user_query))

        transform_events = [e for e in events if isinstance(e, TableTransformEvent)]
        self.assertEqual(len(transform_events), 1)

        transform_event = transform_events[0]
        transformed_df = transform_event.table.to_dataframe()
        pd.testing.assert_frame_equal(transformed_df.reset_index(drop=True), expected_df)

        output_tables = agent.get_output_tables()

        # Second turn: the orchestrator picks up at turn 2 of its script, which is only
        # possible because the conversation history is carried on the agent instance.
        tables_for_plot = {transform_event.table_name: output_tables[transform_event.table_name]}
        user_query2 = UserQueryMultiTablesEvent(
            query="Now make a scatter plot with column x_values as x and column y_values as y",
            tables=tables_for_plot,
            agent_id=agent.id,
        )

        events = list(agent.call_agent(user_query2))
        plot_events = [e for e in events if isinstance(e, PlotGeneratedEvent)]
        self.assertEqual(len(plot_events), 1)

        orchestrator_turns = [turn for kind, turn in scripted.calls if kind == ORCHESTRATOR]
        self.assertEqual(orchestrator_turns, [0, 1, 2, 3])

        self._test_table_agent_ai_service(
            agent,
            expected_tables={transform_event.table_name: Table(expected_df)},
            expected_plots=1,
        )

    def test_multiple_operations_in_single_call(self):
        """Two transformations requested in one turn produce two transform events."""
        sales_df = pd.DataFrame(
            {
                "product": ["A", "B", "C", "D", "E"],
                "sales": [100, 200, 150, 300, 250],
                "region": ["North", "South", "North", "West", "East"],
            }
        )
        inventory_df = pd.DataFrame(
            {
                "product": ["A", "B", "C", "D", "E"],
                "stock": [50, 30, 80, 20, 60],
                "warehouse": ["W1", "W2", "W1", "W3", "W2"],
            }
        )

        agent, _ = self._build_agent(
            {
                ORCHESTRATOR: [
                    ToolCall(
                        "transform_table",
                        {
                            "table_name": "sales_data",
                            "output_table_name": "high_sales_data",
                            "user_request": "Keep sales greater than 150",
                        },
                    ),
                    ToolCall(
                        "transform_table",
                        {
                            "table_name": "inventory_data",
                            "output_table_name": "low_stock_data",
                            "user_request": "Keep stock lower than 50",
                        },
                    ),
                    "Both tables were filtered.",
                ],
                TRANSFORM: [
                    ToolCall(
                        "transform_dataframe",
                        {
                            "code": "transformed_df = df[df['sales'] > 150]",
                            "transformed_table_name": "high_sales_data",
                        },
                    ),
                    ToolCall(
                        "transform_dataframe",
                        {
                            "code": "transformed_df = df[df['stock'] < 50]",
                            "transformed_table_name": "low_stock_data",
                        },
                    ),
                ],
            }
        )

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

        events = list(agent.call_agent(user_query))

        transform_events = [e for e in events if isinstance(e, TableTransformEvent)]
        self.assertEqual(
            len(transform_events), 2, "Should have TWO transform events (both operations)"
        )

        output_tables = agent.get_output_tables()

        self.assertIn("high_sales_data", output_tables, "high_sales_data should be created")
        self.assertIn("low_stock_data", output_tables, "low_stock_data should be created")

        high_sales_df = output_tables["high_sales_data"].get_data()
        self.assertTrue(all(high_sales_df["sales"] > 150), "All sales should be > 150")
        self.assertEqual(len(high_sales_df), 3, "Should have 3 products with sales > 150")

        low_stock_df = output_tables["low_stock_data"].get_data()
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
        """A merge request is delegated to the multi-table sub-agent."""
        sales_df = pd.DataFrame(
            {
                "product": ["A", "B", "C", "D", "E"],
                "sales": [100, 200, 150, 300, 250],
                "region": ["North", "South", "North", "West", "East"],
            }
        )
        inventory_df = pd.DataFrame(
            {
                "product": ["A", "B", "C", "D", "E"],
                "stock": [50, 30, 80, 20, 60],
                "warehouse": ["W1", "W2", "W1", "W3", "W2"],
            }
        )

        merge_code = (
            "result_tables = {'combined_data': pd.merge("
            "tables['sales_data'], tables['inventory_data'], on='product')}"
        )

        agent, _ = self._build_agent(
            {
                ORCHESTRATOR: [
                    ToolCall(
                        "transform_multiple_tables",
                        {
                            "table_names": ["sales_data", "inventory_data"],
                            "output_table_names": ["combined_data"],
                            "user_request": "Merge on product",
                        },
                    ),
                    "The tables were merged.",
                ],
                MULTI_TABLE: [ToolCall("transform_multiple_tables", {"code": merge_code})],
            }
        )

        tables = {"sales_data": Table(sales_df), "inventory_data": Table(inventory_df)}
        user_query = UserQueryMultiTablesEvent(
            query=(
                "Merge the sales_data and inventory_data tables on the 'product' column "
                "and name the result 'combined_data'."
            ),
            tables=tables,
            agent_id=agent.id,
        )

        events = list(agent.call_agent(user_query))

        multi_table_events = [e for e in events if isinstance(e, MultiTableTransformEvent)]
        self.assertEqual(len(multi_table_events), 1, "Should have ONE multi-table transform event")

        output_tables = agent.get_output_tables()
        self.assertIn("combined_data", output_tables, "combined_data should be created")

        combined_df = output_tables["combined_data"].get_data()

        expected_columns = ["product", "sales", "region", "stock", "warehouse"]
        for col in expected_columns:
            self.assertIn(col, combined_df.columns, f"Column {col} should be in combined table")

        self.assertEqual(len(combined_df), 5, "Should have 5 rows after merge")

        self._test_table_agent_ai_service(
            agent,
            expected_tables={"combined_data": Table(combined_df)},
        )

    def test_event_sequence_of_a_delegated_call(self):
        """The emitted event order is the one the chat conversation and replay rely on.

        A response's closing events must come *after* the tool call it made, with the
        sub-agent's own events nested in between, so that
        `AgentEventList.get_agent_and_sub_agents_events` can group them by response window.
        """
        agent, _ = self._build_agent(
            {
                ORCHESTRATOR: [
                    ToolCall(
                        "transform_table",
                        {
                            "table_name": "test_data",
                            "output_table_name": "renamed_data",
                            "user_request": "Rename 'hello' to 'x_values'",
                        },
                    ),
                    "Done.",
                ],
                TRANSFORM: [
                    ToolCall(
                        "transform_dataframe",
                        {"code": RENAME_CODE, "transformed_table_name": "renamed_data"},
                    )
                ],
            }
        )

        user_query = UserQueryMultiTablesEvent(
            query="Rename the column 'hello' to 'x_values'",
            tables={"test_data": Table(pd.DataFrame({"hello": [1], "y_values": [2]}))},
            agent_id=agent.id,
        )

        events = list(agent.call_agent(user_query))
        types = [event.type for event in events]

        # The orchestrator's first response: created, its function call, the whole sub-agent
        # run, the sub-agent success, then the response's closing events.
        self.assertEqual(
            types,
            [
                "user_tables",
                "response_created",
                "function_call",
                "create_sub_agent",
                "user_table_transform",
                "response_created",
                "function_call",
                "code",
                "dataframe_transform",
                "response_full_text",
                "response_completed",
                "sub_agent_success",
                "response_full_text",
                "response_completed",
                "response_created",
                "text_delta",
                "text_delta",
                "response_full_text",
                "response_completed",
            ],
        )

        # The orchestrator's response window must fully contain the sub-agent's events.
        created = [e for e in events if isinstance(e, ResponseCreatedEvent)]
        parent_response_id = created[0].response_id
        completed_index = next(
            i
            for i, e in enumerate(events)
            if isinstance(e, ResponseCompletedEvent) and e.response_id == parent_response_id
        )
        sub_agent_index = next(i for i, e in enumerate(events) if isinstance(e, CreateSubAgent))
        self.assertLess(sub_agent_index, completed_index)

        # Sub-agent success is reported at the parent's level, carrying the parent's call id.
        function_calls = [e for e in events if isinstance(e, FunctionCallEvent)]
        sub_success = next(e for e in events if isinstance(e, SubAgentSuccess))
        self.assertEqual(sub_success.call_id, function_calls[0].call_id)
        self.assertEqual(sub_success.response_id, parent_response_id)

        # Text is streamed as deltas and closed with the accumulated full text.
        deltas = "".join(e.delta for e in events if isinstance(e, TextDeltaEvent))
        self.assertEqual(deltas, "Done.")
        full_texts = [e.text for e in events if isinstance(e, ResponseFullTextEvent)]
        self.assertEqual(full_texts[-1], "Done.")

    def test_tool_error_is_retried_then_succeeds(self):
        """A failing generated code produces an error event, then the model corrects itself."""
        agent, _ = self._build_agent(
            {
                ORCHESTRATOR: [
                    ToolCall(
                        "transform_table",
                        {
                            "table_name": "test_data",
                            "output_table_name": "renamed_data",
                            "user_request": "Rename 'hello' to 'x_values'",
                        },
                    ),
                    "Fixed and done.",
                ],
                TRANSFORM: [
                    # First attempt references an undefined name.
                    ToolCall(
                        "transform_dataframe",
                        {
                            "code": "transformed_df = undefined_name",
                            "transformed_table_name": "renamed_data",
                        },
                    ),
                    ToolCall(
                        "transform_dataframe",
                        {"code": RENAME_CODE, "transformed_table_name": "renamed_data"},
                    ),
                ],
            }
        )

        user_query = UserQueryMultiTablesEvent(
            query="Rename the column 'hello' to 'x_values'",
            tables={"test_data": Table(pd.DataFrame({"hello": [1], "y_values": [2]}))},
            agent_id=agent.id,
        )

        events = list(agent.call_agent(user_query))
        types = [event.type for event in events]

        self.assertIn("function_error", types)
        error_event = next(e for e in events if e.type == "function_error")
        self.assertIn("undefined_name", error_event.message)

        # The retry succeeded, so the transformation still happened.
        transform_events = [e for e in events if isinstance(e, TableTransformEvent)]
        self.assertEqual(len(transform_events), 1)
        self.assertEqual(
            list(transform_events[0].table.to_dataframe().columns), ["x_values", "y_values"]
        )

    def test_missing_table_reports_an_error(self):
        """Referring to a table that was not provided reports an error to the user."""
        agent, _ = self._build_agent(
            {
                ORCHESTRATOR: [
                    ToolCall(
                        "transform_table",
                        {
                            "table_name": "does_not_exist",
                            "output_table_name": "out",
                            "user_request": "Do something",
                        },
                    ),
                    "I could not find that table.",
                ],
            }
        )

        user_query = UserQueryMultiTablesEvent(
            query="Transform the missing table",
            tables={"test_data": Table(pd.DataFrame({"a": [1]}))},
            agent_id=agent.id,
        )

        events = list(agent.call_agent(user_query))

        error_events = [e for e in events if e.type == "function_error"]
        self.assertEqual(len(error_events), 1)
        self.assertIn("does_not_exist", error_events[0].message)

    def test_call_agent_async_streams_the_same_events(self):
        """The async entry point streams the same events as the synchronous one.

        It is the path an HTTP route would drive the agent through, so it must not diverge.
        """
        script = {
            ORCHESTRATOR: [
                ToolCall(
                    "transform_table",
                    {
                        "table_name": "test_data",
                        "output_table_name": "renamed_data",
                        "user_request": "Rename 'hello' to 'x_values'",
                    },
                ),
                "Done.",
            ],
            TRANSFORM: [
                ToolCall(
                    "transform_dataframe",
                    {"code": RENAME_CODE, "transformed_table_name": "renamed_data"},
                )
            ],
        }

        def build_query(agent: TableAgentAi) -> UserQueryMultiTablesEvent:
            return UserQueryMultiTablesEvent(
                query="Rename the column 'hello' to 'x_values'",
                tables={"test_data": Table(pd.DataFrame({"hello": [1], "y_values": [2]}))},
                agent_id=agent.id,
            )

        sync_agent, _ = self._build_agent(script)
        sync_types = [e.type for e in sync_agent.call_agent(build_query(sync_agent))]

        async_agent, _ = self._build_agent(script)

        async def collect() -> list[str]:
            return [
                event.type
                async for event in async_agent.call_agent_async(build_query(async_agent))
            ]

        async_types = asyncio.run(collect())

        self.assertEqual(async_types, sync_types)

    def test_model_is_configured_as_a_provider_model_string(self):
        """The agent reports its model as a 'provider:model' string."""
        agent = TableAgentAi(openai_api_key="key", model="openai:gpt-4o", temperature=0.2)
        self.assertEqual(agent.get_model(), "openai:gpt-4o")
        self.assertEqual(agent.get_temperature(), 0.2)

        # A bare model name stays readable, for configurations saved before the migration.
        legacy_agent = TableAgentAi(openai_api_key="key", model="gpt-4o", temperature=0.2)
        self.assertEqual(legacy_agent.get_model(), "openai:gpt-4o")

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
