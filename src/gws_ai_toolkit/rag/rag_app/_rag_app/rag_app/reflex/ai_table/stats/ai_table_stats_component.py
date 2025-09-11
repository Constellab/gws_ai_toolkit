import reflex as rx

from .ai_table_stats_state import AiTableStatsState
from .ai_table_stats_type import AiTableStatsResults


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
        # Figure (if it exists)
        rx.cond(
            test_result.figure,
            rx.plotly(test_result.figure, width="100%", height="300px")
        ),
        padding="0.5em",
        width="100%",
    )


def _show_additional_test_suggestion() -> rx.Component:
    """Display suggested additional test if available."""
    return rx.cond(
        AiTableStatsState.has_suggested_additional_test,
        rx.box(
            rx.heading("Suggested Additional Test", size="3", margin_bottom="0.5em", margin_top="1em"),
            rx.box(
                rx.text(
                    f"Based on your analysis, you might want to run: {AiTableStatsState.suggested_additional_test}",
                    margin_bottom="0.5em"
                ),
                # Show reference column input for pairwise test
                rx.cond(
                    AiTableStatsState.suggested_additional_test == "Student t-test (independent paired wise)",
                    rx.form(
                        rx.vstack(
                            rx.cond(
                                AiTableStatsState.last_run_config.group_input,
                                rx.text("Reference group (Optional):", font_weight="bold", font_size="0.9em"),
                                rx.text("Reference Column (Optional):", font_weight="bold", font_size="0.9em")
                            ),
                            rx.cond(
                                AiTableStatsState.last_run_config.group_input,
                                rx.text(
                                    "Specify a group name to compare against all other groups",
                                    font_size="0.8em", color="gray", margin_bottom="0.5em"),
                                rx.text(
                                    "Specify a reference column to compare against all others (instead of all combinations)",
                                    font_size="0.8em", color="gray", margin_bottom="0.5em")
                            ),
                            rx.input(
                                placeholder=rx.cond(
                                    AiTableStatsState.last_run_config.group_input,
                                    "e.g., 'control' - leave empty for all combinations",
                                    "e.g., 'control_group' - leave empty for all combinations"
                                ),
                                name="reference_column",
                                width="100%",
                                size="2"
                            ),
                            rx.button(
                                rx.cond(
                                    AiTableStatsState.is_processing,
                                    rx.hstack(
                                        rx.spinner(size="1"),
                                        rx.text("Running..."),
                                        spacing="2",
                                        align_items="center"
                                    ),
                                    rx.text(f"Run {AiTableStatsState.suggested_additional_test}")
                                ),
                                type="submit",
                                cursor="pointer",
                                disabled=AiTableStatsState.is_processing
                            ),
                            spacing="2"
                        ),
                        on_submit=AiTableStatsState.run_additional_test_with_reference_column,
                        reset_on_submit=True
                    ),
                    # For other tests, show simple button
                    rx.button(
                        rx.cond(
                            AiTableStatsState.is_processing,
                            rx.hstack(
                                rx.spinner(size="1"),
                                rx.text("Running..."),
                                spacing="2",
                                align_items="center"
                            ),
                            rx.text(f"Run {AiTableStatsState.suggested_additional_test}")
                        ),
                        on_click=lambda: AiTableStatsState.run_additional_test(
                            AiTableStatsState.suggested_additional_test),
                        color_scheme="green",
                        cursor="pointer",
                        disabled=AiTableStatsState.is_processing
                    )
                ),
                padding="0.8em",
                border="1px solid var(--green-6)",
                border_radius="8px",
                background_color="var(--green-2)"
            ),
            width="100%"
        )
    )


def _show_last_run_config() -> rx.Component:
    """Display the last run configuration (excluding ai_prompt)."""
    return rx.cond(
        AiTableStatsState.last_run_config,
        rx.box(
            rx.heading("Configuration", size="3", margin_bottom="0.5em", margin_top="1em"),
            rx.vstack(
                rx.hstack(
                    rx.text("Columns:", font_weight="bold", font_size="0.9em"),
                    rx.text(
                        AiTableStatsState.last_run_config.str_columns,
                        font_size="0.9em"
                    ),
                    spacing="2"
                ),
                rx.hstack(
                    rx.text("Group Input:", font_weight="bold", font_size="0.9em"),
                    rx.text(
                        rx.cond(
                            AiTableStatsState.last_run_config.group_input,
                            AiTableStatsState.last_run_config.group_input,
                            "None"
                        ),
                        font_size="0.9em"
                    ),
                    spacing="2"
                ),
                rx.hstack(
                    rx.text("Columns are Paired:", font_weight="bold", font_size="0.9em"),
                    rx.text(
                        rx.cond(
                            AiTableStatsState.last_run_config.columns_are_paired,
                            "Yes",
                            "No"
                        ),
                        font_size="0.9em"
                    ),
                    spacing="2"
                ),
                spacing="1",
                padding="1em",
            ),
            width="100%"
        )
    )


def _show_results() -> rx.Component:
    return rx.fragment(
        _show_last_run_config(),
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
        ),
        _show_additional_test_suggestion()
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
                        type="submit", cursor="pointer", disabled=AiTableStatsState.is_processing),
                    spacing="2", margin_top="0.5em",),
                spacing="3", align="stretch",),
            on_submit=AiTableStatsState.process_ai_prompt, reset_on_submit=False,),
        _show_results(),
        padding="1em", width="100%", overflow="auto",)
