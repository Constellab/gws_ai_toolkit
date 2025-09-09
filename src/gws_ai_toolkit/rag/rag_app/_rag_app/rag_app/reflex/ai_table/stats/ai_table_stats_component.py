import reflex as rx

from .ai_table_stats_state import AiTableStatsState


def ai_table_stats_component():
    return rx.box(
        rx.hstack(
            rx.heading("Column Statistics", size="4"),
            rx.spacer(),
            rx.button(
                "Clear Results",
                on_click=AiTableStatsState.clear_test_results,
                color_scheme="red",
                variant="outline",
            ),
            align_items="center",
            margin_bottom="1em"
        ),
        rx.form(
            rx.vstack(
                rx.text("Enter column names (separated by commas):"),
                rx.input(
                    placeholder="e.g., name, age, email, status",
                    name="columns_input",
                    width="100%",
                ),
                rx.checkbox(
                    "Columns are paired",
                    name="columns_are_paired",
                    default_checked=False,
                ),
                rx.hstack(
                    rx.button(
                        "Submit",
                        type="submit",
                        color_scheme="blue",
                    ),

                    spacing="2",
                    margin_top="0.5em",
                ),
                spacing="3",
                align="stretch",
            ),
            on_submit=AiTableStatsState.submit_columns,
            reset_on_submit=False,
        ),
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
                width="100%",
            )
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
                width="100%",
            )
        ),
        padding="1em",
        width="100%",
        overflow="auto",
    )
