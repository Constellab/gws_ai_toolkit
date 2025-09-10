import reflex as rx

from .ai_table_stats_state import AiTableStatsState
from .ai_table_stats_tests import AiTableStatsResults


def _show_test_result(test_result: AiTableStatsResults) -> rx.Component:
    """Display a single test result with result_text, test_name, and optional statistics."""
    return rx.box(
        # Main result text (most important)
        rx.text(
            test_result.result_text,
        ),
        # Test name
        rx.text(
            f"Test: {test_result.test_name}",
            font_size="0.8em",
            color="var(--gray-9)"
        ),
        # Statistics (if they exist)
        rx.cond(
            (test_result.statistic != None) & (test_result.p_value != None),
            rx.hstack(
                rx.text(
                    f"Statistic: {test_result.statistic_scientific}",
                    font_size="0.8em",
                    color="var(--gray-9)"
                ),
                rx.text(
                    f"p-value: {test_result.p_value_scientific}",
                    font_size="0.8em",
                    color="var(--gray-9)"
                ),
                spacing="4"
            )
        ),
        padding="0.5em",
    )


def _show_results() -> rx.Component:
    return rx.fragment(
        rx.cond(
            AiTableStatsState.last_test_result,
            rx.box(
                rx.heading("Last Test Result", size="3", margin_bottom="0.5em", margin_top="1em"),
                _show_test_result(AiTableStatsState.last_test_result),
                width="100%"
            )
        ),
        rx.cond(
            AiTableStatsState.test_history.length() > 0,
            rx.box(
                rx.heading("Complete Test History", size="3", margin_bottom="0.5em", margin_top="1em"),
                rx.vstack(
                    rx.foreach(
                        AiTableStatsState.test_history,
                        _show_test_result
                    ),
                    spacing="2",
                    width="100%"
                ),
                width="100%"
            )
        )
    )


def ai_table_stats_component():
    return rx.box(
        rx.hstack(
            rx.heading("Column Statistics", size="4"),
            rx.spacer(),
            rx.button(
                "Clear Results", on_click=AiTableStatsState.clear_test_results,
                color_scheme="red", variant="outline", cursor="pointer"),
            align_items="center", margin_bottom="1em"),
        rx.form(
            rx.vstack(
                rx.text("Describe your analysis in natural language:", font_weight="bold"),
                rx.text(
                    "Examples: 'Compare age and salary', 'Analyze revenue grouped by region', 'Test if before and after scores are paired'",
                    font_size="0.9em", color="gray", margin_bottom="0.5em"),
                rx.input(
                    placeholder="e.g., 'Compare the sales and profit columns' or 'Analyze customer satisfaction grouped by product category'",
                    name="ai_prompt", width="100%"),
                rx.hstack(
                    rx.button(
                        rx.cond(
                            AiTableStatsState.is_processing, rx.hstack(
                                rx.spinner(size="1"),
                                rx.text("Processing..."),
                                spacing="2", align_items="center"),
                            rx.text("Analyze with AI")),
                        type="submit", color_scheme="blue", cursor="pointer", disabled=AiTableStatsState.is_processing),
                    spacing="2", margin_top="0.5em",),
                spacing="3", align="stretch",),
            on_submit=AiTableStatsState.process_ai_prompt, reset_on_submit=False,),
        _show_results(),
        padding="1em", width="100%", overflow="auto",)
