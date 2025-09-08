import reflex as rx
import reflex_enterprise as rxe

from .ai_table_data_state import AiTableDataState


def table_section():
    """Component for data visualization section"""
    return rx.box(
        rxe.ag_grid(
            id="ai_table_ag_grid",
            column_defs=AiTableDataState.ag_grid_column_defs,
            row_data=AiTableDataState.ag_grid_row_data,
            theme="quartz",
            width="100%",
            height="100%",
        ),
        width="100%",
        height="100%",
        padding="1em",
    )
