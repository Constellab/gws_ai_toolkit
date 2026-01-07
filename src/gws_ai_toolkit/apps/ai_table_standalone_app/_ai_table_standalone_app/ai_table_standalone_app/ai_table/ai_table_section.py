import reflex as rx
import reflex_enterprise as rxe

from .ai_table_data_state import AiTableDataState
from .selection.ai_table_selection_dialog import ai_table_selection_dialog
from .selection.ai_table_selection_state import AiTableSelectionState


def table_section():
    """Component for data visualization section"""
    return rx.vstack(
        # Custom CSS for dense headers
        rx.html("""
            <style>
                .dense-header {
                    font-size: 10px;
                    line-height: 1.2;
                    padding: 4px;
                    height: 50px;
                    max-height: 50px;
                }
                .dense-header .ag-header-cell-text {
                    display: -webkit-box;
                    -webkit-line-clamp: 2;
                    -webkit-box-orient: vertical;
                    overflow: hidden;
                    text-overflow: ellipsis;
                }
            </style>
        """),
        # Table info and extract button
        rx.hstack(
            rx.text(f"Rows: {AiTableDataState.nb_rows}", font_weight="bold", color="blue.600"),
            rx.text(
                f"Columns: {AiTableDataState.nb_columns}", font_weight="bold", color="blue.600"
            ),
            rx.text(
                f"Table: {AiTableDataState.current_table_name}",
                font_weight="bold",
                color="green.600",
            ),
            rx.spacer(),
            # Column width controls
            rx.menu.root(
                rx.menu.trigger(
                    rx.button(
                        rx.cond(
                            AiTableDataState.column_size_mode == "default",
                            "View: Default",
                            "View: Dense",
                        ),
                        size="2",
                        variant="soft",
                    ),
                ),
                rx.menu.content(
                    rx.menu.item(
                        "Default",
                        on_click=AiTableDataState.set_column_size_default,
                    ),
                    rx.menu.item(
                        "Dense",
                        on_click=AiTableDataState.set_column_size_dense,
                    ),
                ),
            ),
            # Zoom controls
            rx.hstack(
                rx.button(
                    "-",
                    on_click=AiTableDataState.zoom_out,
                    size="2",
                    variant="soft",
                ),
                rx.text(
                    f"{AiTableDataState.zoom_level * 100:.0f}%",
                    font_weight="bold",
                    min_width="60px",
                    text_align="center",
                ),
                rx.button(
                    "+",
                    on_click=AiTableDataState.zoom_in,
                    size="2",
                    variant="soft",
                ),
                spacing="2",
                align="center",
            ),
            rx.button(
                "Extract Selection",
                on_click=AiTableSelectionState.open_extract_dialog,
                disabled=~AiTableSelectionState.can_extract,
                variant="outline",
            ),
            rx.button(
                "Download Table",
                on_click=AiTableDataState.download_current_table,
                disabled=~AiTableDataState.dataframe_loaded,
                variant="outline",
            ),
            spacing="4",
            align="center",
            padding="0.5em 1em",
        ),
        # AG Grid with selection enabled
        rx.box(
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
                    key=f"ag_grid_{AiTableDataState.column_size_mode}",
                    # auto_size_strategy=AiTableDataState.ag_grid_auto_size_strategy,
                    tooltip_show_delay=200,  # Show tooltip after 200ms (default is 2000ms)
                    tooltip_hide_delay=0,  # Hide tooltip immediately when mouse leaves (default is 10000ms)
                ),
                width=f"calc(100% / {AiTableDataState.zoom_level})",
                height=f"calc(100% / {AiTableDataState.zoom_level})",
                style={
                    "transform": f"scale({AiTableDataState.zoom_level})",
                    "transform-origin": "top left",
                },
                class_name="ag-grid-zoom-container",
            ),
            width="100%",
            flex="1",
            min_height="0",
            padding="0 1em 1em 1em",
            overflow="hidden",
        ),
        # Extract dialog
        ai_table_selection_dialog(),
        height="100%",
        width="100%",
        spacing="0",
    )
