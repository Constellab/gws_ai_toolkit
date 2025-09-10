import reflex as rx

from .ai_table_stats_state import AiTableStatsState


def _show_results() -> rx.Component:
    return rx.fragment(
        rx.cond(
            AiTableStatsState.last_test_json != "",
            rx.box(
                rx.heading("Last Test Result", size="3", margin_bottom="0.5em", margin_top="1em"),
                rx.code_block(
                    AiTableStatsState.last_test_json,
                    language="json",
                    width="100%",
                    max_height="300px",
                    overflow="auto",
                    font_size="0.8em",
                ),
                width="100%",)
        ),
        rx.cond(
            AiTableStatsState.test_history_json != "",
            rx.box(
                rx.heading("Complete Test History", size="3", margin_bottom="0.5em", margin_top="1em"),
                rx.code_block(
                    AiTableStatsState.test_history_json,
                    language="json",
                    width="100%",
                    max_height="400px",
                    overflow="auto",
                    font_size="0.8em",
                ),
                width="100%",)
        )
    )


def ai_table_stats_component():
    return rx.box(
        rx.hstack(
            rx.heading("Column Statistics", size="4"),
            rx.spacer(),
            rx.button(
                "Clear Results", on_click=AiTableStatsState.clear_test_results, color_scheme="red", variant="outline",),
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
                                spacing="2"),
                            rx.text("Analyze with AI")),
                        type="submit", color_scheme="blue", disabled=AiTableStatsState.is_processing,),
                    spacing="2", margin_top="0.5em",),
                spacing="3", align="stretch",),
            on_submit=AiTableStatsState.process_ai_prompt, reset_on_submit=False,),
        _show_results(),
        padding="1em", width="100%", overflow="auto",)
