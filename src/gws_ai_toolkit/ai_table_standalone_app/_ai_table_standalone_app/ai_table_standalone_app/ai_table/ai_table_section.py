import reflex as rx
import reflex_enterprise as rxe

from .ai_table_data_state import AiTableDataState
from .selection.ai_table_selection_dialog import ai_table_selection_dialog
from .selection.ai_table_selection_state import AiTableSelectionState


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
                on_click=AiTableSelectionState.open_extract_dialog,
                disabled=~AiTableSelectionState.can_extract,
                variant="outline",
                cursor="pointer",
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
                on_cell_selection_changed=AiTableSelectionState.on_cell_selection_changed,
                cell_selection=True,
                theme="quartz",
                width="100%",
                height="100%",
            ),
            width="100%",
            flex='1',
            min_height='0',
            padding="0 1em 1em 1em"
        ),
        # Extract dialog
        ai_table_selection_dialog(),
        height="100%",
        width="100%",
        spacing="0"
    )
