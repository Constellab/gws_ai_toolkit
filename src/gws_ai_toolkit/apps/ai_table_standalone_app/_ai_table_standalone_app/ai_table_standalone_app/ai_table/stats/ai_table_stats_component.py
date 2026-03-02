import reflex as rx
from gws_ai_toolkit.stats.ai_table_stats_type import AiTableStatsResults
from gws_reflex_base import plotly_fullscreen_dialog, plotly_with_fullscreen

from .ai_table_stats_state import AiTableStatsState


def _user_message_bubble() -> rx.Component:
    """Display the user's submitted prompt as a right-aligned chat bubble."""
    return rx.box(
        rx.hstack(
            rx.spacer(),
            rx.box(
                rx.text(
                    AiTableStatsState.submitted_prompt,
                    color="white",
                    font_size="0.9em",
                ),
                background_color="var(--accent-9)",
                padding="0.6em 1em",
                border_radius="12px 12px 2px 12px",
                max_width="85%",
            ),
            width="100%",
        ),
        width="100%",
        margin_bottom="1em",
    )


def _assistant_message_bubble(content: rx.Component) -> rx.Component:
    """Wrap content in a left-aligned assistant-style bubble."""
    return rx.box(
        rx.hstack(
            rx.box(
                content,
                background_color="var(--gray-3)",
                padding="0.8em 1em",
                border_radius="12px 12px 12px 2px",
                max_width="90%",
                width="fit-content",
            ),
            rx.spacer(),
            width="100%",
        ),
        width="100%",
        margin_bottom="0.5em",
    )


def _processing_indicator() -> rx.Component:
    """Show a loading indicator while processing."""
    return _assistant_message_bubble(
        rx.hstack(
            rx.spinner(size="1"),
            rx.text("Analyzing...", font_size="0.85em", color="var(--gray-10)"),
            spacing="2",
            align_items="center",
        ),
    )


def _ai_summary_bubble() -> rx.Component:
    """Display the AI summary response as an assistant message."""
    return _assistant_message_bubble(
        rx.markdown(
            AiTableStatsState.ai_summary_response,
            class_name="dense-markdown",
            font_size="0.85em",
        ),
    )


def _form_prompt() -> rx.Component:
    """Input form displayed when no prompt has been submitted yet."""
    return rx.form(
        rx.vstack(
            rx.text("Describe your analysis in natural language:", font_weight="bold"),
            rx.list.unordered(
                rx.list.item("Compare age and salary"),
                rx.list.item("Analyze revenue grouped by region"),
                rx.list.item("Test if before and after scores are paired"),
                rx.list.item("What is the correlation between height and weight?"),
                font_size="0.8em",
                color="gray",
                margin_bottom="0.5em",
            ),
            rx.input(
                placeholder="e.g., 'Compare the sales and profit columns'",
                name="ai_prompt",
                width="100%",
            ),
            rx.button(
                rx.text("Analyze with AI"),
                type="submit",
                cursor="pointer",
            ),
            spacing="3",
            align="stretch",
        ),
        on_submit=AiTableStatsState.process_ai_prompt,
        reset_on_submit=True,
    )


def _chat_input() -> rx.Component:
    """Bottom-pinned input for follow-up analysis after initial submission."""
    return rx.form(
        rx.hstack(
            rx.input(
                placeholder="Ask another analysis question...",
                name="ai_prompt",
                width="100%",
                size="2",
                disabled=AiTableStatsState.is_processing,
            ),
            rx.button(
                rx.cond(
                    AiTableStatsState.is_processing,
                    rx.spinner(size="1"),
                    rx.icon("send", size=14),
                ),
                type="submit",
                cursor="pointer",
                disabled=AiTableStatsState.is_processing,
                size="2",
            ),
            spacing="2",
            width="100%",
            align_items="center",
        ),
        on_submit=AiTableStatsState.process_ai_prompt,
        reset_on_submit=True,
        width="100%",
    )


def _show_test_result(test_result: AiTableStatsResults) -> rx.Component:
    """Display a single test result with result_text, test_name, and optional statistics."""
    return rx.box(
        rx.text(
            test_result.result_text,
        ),
        rx.text(f"Test: {test_result.test_name}", font_size="0.8em", color="var(--gray-9)"),
        rx.cond(
            (test_result.statistic is not None) & (test_result.p_value is not None),
            rx.hstack(
                rx.text(
                    f"Statistic: {test_result.statistic_scientific}",
                    font_size="0.8em",
                    color="var(--gray-9)",
                ),
                rx.text(
                    f"p-value: {test_result.p_value_scientific}",
                    font_size="0.8em",
                    color="var(--gray-9)",
                ),
                spacing="4",
            ),
        ),
        rx.cond(
            test_result.result_figure,
            plotly_with_fullscreen(
                figure=test_result.result_figure,
                plot_name=test_result.test_name,
            ),
        ),
        padding="0.5em",
        width="100%",
    )


def _show_additional_test_suggestion() -> rx.Component:
    """Display suggested additional test if available."""
    return rx.cond(
        AiTableStatsState.has_suggested_additional_test,
        _assistant_message_bubble(
            rx.vstack(
                rx.text(
                    f"Based on your analysis, you might want to run: "
                    f"{AiTableStatsState.suggested_additional_test}",
                    font_size="0.85em",
                    margin_bottom="0.5em",
                ),
                rx.form(
                    rx.vstack(
                        rx.cond(
                            AiTableStatsState.last_run_config.group_input,
                            rx.text(
                                "Reference group (Optional):",
                                font_weight="bold",
                                font_size="0.85em",
                            ),
                            rx.text(
                                "Reference Column (Optional):",
                                font_weight="bold",
                                font_size="0.85em",
                            ),
                        ),
                        rx.cond(
                            AiTableStatsState.last_run_config.group_input,
                            rx.text(
                                "Specify a group name to compare against all other groups",
                                font_size="0.8em",
                                color="var(--gray-9)",
                            ),
                            rx.text(
                                "Specify a reference column to compare against all others",
                                font_size="0.8em",
                                color="var(--gray-9)",
                            ),
                        ),
                        rx.input(
                            placeholder=rx.cond(
                                AiTableStatsState.last_run_config.group_input,
                                "e.g., 'control' - leave empty for all combinations",
                                "e.g., 'control_group' - leave empty for all combinations",
                            ),
                            name="reference_column",
                            width="100%",
                            size="1",
                        ),
                        rx.button(
                            rx.cond(
                                AiTableStatsState.is_processing,
                                rx.hstack(
                                    rx.spinner(size="1"),
                                    rx.text("Running..."),
                                    spacing="2",
                                    align_items="center",
                                ),
                                rx.text(f"Run {AiTableStatsState.suggested_additional_test}"),
                            ),
                            type="submit",
                            size="1",
                            disabled=AiTableStatsState.is_processing,
                        ),
                        spacing="2",
                    ),
                    on_submit=AiTableStatsState.run_additional_test_with_reference_column,
                    reset_on_submit=True,
                ),
                spacing="2",
                width="100%",
            ),
        ),
    )


def _show_details_accordion() -> rx.Component:
    """Collapsible details section with run config and test history."""
    return rx.cond(
        AiTableStatsState.test_history.length() > 0,
        rx.accordion.root(
            rx.accordion.item(
                header="Details",
                content=rx.accordion.content(
                    _show_last_run_config(),
                    rx.box(
                        rx.heading(
                            "Complete Test History",
                            size="3",
                            margin_bottom="0.5em",
                            margin_top="1em",
                        ),
                        rx.vstack(
                            rx.foreach(AiTableStatsState.test_history, _show_test_result),
                            spacing="2",
                            width="100%",
                        ),
                        width="100%",
                    ),
                ),
            ),
            collapsible=True,
            width="100%",
            variant="soft",
            margin_top="0.5em",
        ),
    )


def _show_last_run_config() -> rx.Component:
    """Display the last run configuration."""
    return rx.cond(
        AiTableStatsState.last_run_config,
        rx.box(
            rx.heading("Configuration", size="3", margin_bottom="0.5em"),
            rx.vstack(
                rx.hstack(
                    rx.text("Columns:", font_weight="bold", font_size="0.85em"),
                    rx.text(AiTableStatsState.last_run_config.str_columns, font_size="0.85em"),
                    spacing="2",
                ),
                rx.hstack(
                    rx.text("Group Input:", font_weight="bold", font_size="0.85em"),
                    rx.text(
                        rx.cond(
                            AiTableStatsState.last_run_config.group_input,
                            AiTableStatsState.last_run_config.group_input,
                            "None",
                        ),
                        font_size="0.85em",
                    ),
                    spacing="2",
                ),
                rx.hstack(
                    rx.text("Columns are Paired:", font_weight="bold", font_size="0.85em"),
                    rx.text(
                        rx.cond(AiTableStatsState.last_run_config.columns_are_paired, "Yes", "No"),
                        font_size="0.85em",
                    ),
                    spacing="2",
                ),
                rx.hstack(
                    rx.text("Relation Analysis:", font_weight="bold", font_size="0.85em"),
                    rx.text(
                        rx.cond(
                            AiTableStatsState.last_run_config.relation,
                            "Yes (Correlation tests)",
                            "No (Standard tests)",
                        ),
                        font_size="0.85em",
                    ),
                    spacing="2",
                ),
                rx.hstack(
                    rx.text("Reference column:", font_weight="bold", font_size="0.85em"),
                    rx.text(
                        rx.cond(
                            AiTableStatsState.last_run_config.reference_column,
                            AiTableStatsState.last_run_config.reference_column,
                            "None",
                        ),
                        font_size="0.85em",
                    ),
                    spacing="2",
                ),
                spacing="1",
            ),
            width="100%",
        ),
    )


def _chat_conversation() -> rx.Component:
    """The chat-like conversation view shown after a prompt is submitted."""
    return rx.vstack(
        # User message bubble (right-aligned)
        _user_message_bubble(),
        # Processing indicator (while running)
        rx.cond(
            AiTableStatsState.is_processing,
            _processing_indicator(),
        ),
        # AI summary response
        rx.cond(
            AiTableStatsState.ai_summary_response,
            _ai_summary_bubble(),
        ),
        # Suggested additional test
        _show_additional_test_suggestion(),
        # Details accordion
        _show_details_accordion(),
        plotly_fullscreen_dialog(),
        spacing="1",
        width="100%",
        flex="1",
        overflow_y="auto",
        padding_bottom="0.5em",
    )


def ai_table_stats_component():
    return rx.box(
        # Header
        rx.hstack(
            rx.heading("Column Statistics", size="4"),
            rx.spacer(),
            rx.button(
                rx.icon("plus", size=14),
                "New Analysis",
                on_click=AiTableStatsState.clear_test_results,
                variant="outline",
                cursor="pointer",
            ),
            align_items="center",
            margin_bottom="1em",
            flex_shrink="0",
        ),
        # Main content: either the initial form or the chat conversation
        rx.cond(
            AiTableStatsState.submitted_prompt,
            # Chat-like conversation view
            rx.vstack(
                _chat_conversation(),
                # Bottom-pinned input for follow-up
                _chat_input(),
                flex="1",
                min_height="0",
                width="100%",
                spacing="2",
            ),
            # Initial form view
            _form_prompt(),
        ),
        padding="1em",
        width="100%",
        height="100%",
        display="flex",
        flex_direction="column",
        overflow="hidden",
    )
