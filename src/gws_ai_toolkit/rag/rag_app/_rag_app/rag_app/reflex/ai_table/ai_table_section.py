import reflex as rx
import reflex_enterprise as rxe

from .ai_table_data_state import AiTableDataState


def extract_dialog():
    """Dialog component for extracting table selection"""
    return rx.dialog.root(
        rx.dialog.content(
            rx.dialog.title("Extract Table Selection"),
            rx.dialog.description("Configure how to extract the selected data"),
            rx.vstack(
                rx.text(AiTableDataState.selection_info, font_weight="bold", color="blue.600"),
                rx.hstack(
                    rx.checkbox(
                        "Use first row as header",
                        checked=AiTableDataState.use_first_row_as_header,
                        on_change=AiTableDataState.toggle_first_row_as_header,
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
                        ),
                        on_click=AiTableDataState.close_extract_dialog,
                    ),
                    rx.dialog.close(
                        rx.button(
                            "Extract",
                            variant="solid",
                            color_scheme="green",
                        ),
                        on_click=AiTableDataState.extract_selection,
                    ),
                    spacing="2",
                    justify="end",
                ),
                spacing="4",
                align="stretch",
            ),
            max_width="500px",
        ),
        open=AiTableDataState.extract_dialog_open,
        on_open_change=AiTableDataState.close_extract_dialog,
    )


def table_section():
    """Component for data visualization section"""
    return rx.vstack(
        # Table info and extract button
        rx.hstack(
            rx.text(f"Rows: {AiTableDataState.nb_rows}", font_weight="bold", color="blue.600"),
            rx.text(f"Columns: {AiTableDataState.nb_columns}", font_weight="bold", color="blue.600"),
            rx.text(f"Table: {AiTableDataState.current_table_name}", font_weight="bold", color="green.600"),
            rx.spacer(),
            rx.button(
                "Extract Selection",
                on_click=AiTableDataState.open_extract_dialog,
                disabled=AiTableDataState.can_extract == False,
                variant="outline",
                color_scheme="green",
            ),
            spacing="4",
            align="center",
            padding="0.5em 1em",
        ),
        # AG Grid with selection enabled
        rx.box(
            rxe.ag_grid(
                id="ai_table_ag_grid",
                column_defs=AiTableDataState.ag_grid_column_defs,
                row_data=AiTableDataState.ag_grid_row_data,
                on_cell_selection_changed=AiTableDataState.on_cell_selection_changed,
                cell_selection=True,
                theme="quartz",
                width="100%",
                height="100%",
            ),
            width="100%",
            flex='1',
            min_height='0'
        ),
        # Extract dialog
        extract_dialog(),
        height="100%",
        width="100%",
        spacing="0"
    )
