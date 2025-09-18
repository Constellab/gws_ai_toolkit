import reflex as rx

from .ai_table_selection_state import AiTableSelectionState


def ai_table_selection_dialog():
    """Dialog component for extracting table selection"""
    return rx.dialog.root(
        rx.dialog.content(
            rx.dialog.title("Extract Table Selection"),
            rx.dialog.description("Configure how to extract the selected data"),
            rx.vstack(
                rx.text(AiTableSelectionState.selection_info, font_weight="bold", color="blue.600"),
                rx.hstack(
                    rx.checkbox(
                        "Use first row as header",
                        checked=AiTableSelectionState.use_first_row_as_header,
                        on_change=AiTableSelectionState.toggle_first_row_as_header,
                    ),
                    spacing="2",
                    align="center",
                ),
                rx.hstack(
                    rx.dialog.close(
                        rx.button(
                            "Cancel",
                            variant="outline",
                            color_scheme="gray",
                            cursor="pointer",
                        ),
                        on_click=AiTableSelectionState.close_extract_dialog,
                    ),
                    rx.dialog.close(
                        rx.button(
                            "Extract",
                            variant="solid",
                            cursor="pointer",
                        ),
                        on_click=AiTableSelectionState.extract_selection,
                    ),
                    spacing="2",
                    justify="end",
                ),
                spacing="4",
                align="stretch",
            ),
            max_width="500px",
        ),
        open=AiTableSelectionState.extract_dialog_open,
        on_open_change=AiTableSelectionState.close_extract_dialog,
    )
