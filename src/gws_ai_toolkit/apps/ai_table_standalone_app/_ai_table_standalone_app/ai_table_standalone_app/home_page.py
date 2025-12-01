import reflex as rx

from .ai_table.ai_table_data_state import AiTableDataState
from .main_state import MainState


def uploaded_files_list():
    """Display list of uploaded files with option to select current file"""
    return rx.cond(
        AiTableDataState.dataframe_loaded,
        rx.vstack(
            rx.heading("Uploaded Files", size="4"),
            rx.vstack(
                # All tables
                rx.foreach(
                    AiTableDataState.excel_file_list,
                    lambda table: rx.hstack(
                        rx.text(table["name"], font_weight="medium"),
                        rx.button(
                            "Open in AI Table",
                            size="1",
                            variant="outline",
                            on_click=[
                                AiTableDataState.select_excel_file(table["id"]),
                                rx.redirect("/ai-table"),
                            ],
                        ),
                        justify="between",
                        align="center",
                        width="100%",
                        padding="0.5em",
                        border="1px solid var(--gray-6)",
                        border_radius="0.375rem",
                    ),
                ),
                spacing="2",
                width="100%",
            ),
            spacing="3",
            width="100%",
        ),
        rx.box(),
    )


def upload_section():
    """Component for file upload section"""
    return rx.vstack(
        rx.cond(
            MainState.is_uploading,
            rx.vstack(
                rx.spinner(size="3"),
                rx.text(
                    "Uploading files...",
                    font_size="lg",
                    color="var(--gray-11)",
                ),
                align="center",
                justify="center",
                spacing="3",
                width="100%",
                height="12rem",
                border_width="2px",
                border_style="dashed",
                border_color="var(--accent-10)",
                border_radius="0.75rem",
                background_color="var(--accent-2)",
            ),
            rx.upload.root(
                rx.box(
                    rx.icon(
                        tag="upload",
                        style={
                            "width": "3rem",
                            "height": "3rem",
                            "color": "var(--accent-10)",
                            "margin_bottom": "0.75rem",
                        },
                    ),
                    rx.vstack(
                        rx.hstack(
                            rx.text(
                                "Click to upload",
                                style={"font_weight": "bold", "color": "var(--accent-10)"},
                            ),
                            rx.text(
                                " or drag and drop",
                                style={"color": "var(--gray-10)"},
                            ),
                            spacing="1",
                        ),
                        rx.text(
                            "CSV, Excel files (.csv, .xls, .xlsx) - Multiple files supported",
                            style={
                                "font_size": "0.875rem",
                                "color": "var(--gray-10)",
                                "margin_top": "0.25rem",
                            },
                        ),
                        align="center",
                        spacing="1",
                    ),
                    style={
                        "display": "flex",
                        "flex_direction": "column",
                        "align_items": "center",
                        "justify_content": "center",
                        "padding": "2rem",
                        "text_align": "center",
                    },
                ),
                id="upload",
                accept={
                    "text/csv": [".csv"],
                    "application/vnd.ms-excel": [".xls"],
                    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet": [".xlsx"],
                },
                max_files=10,
                on_drop=MainState.handle_upload(rx.upload_files(on_upload_progress=MainState.handle_upload_progress)),
                style={
                    "width": "100%",
                    "height": "12rem",
                    "border_width": "2px",
                    "border_style": "dashed",
                    "border_color": "var(--accent-10)",
                    "border_radius": "0.75rem",
                    "cursor": "pointer",
                    "transition_property": "all",
                    "transition_duration": "0.2s",
                    "transition_timing_function": "ease-in-out",
                    "display": "flex",
                    "align_items": "center",
                    "justify_content": "center",
                    "background_color": "white",
                    "_hover": {
                        "background_color": "var(--accent-2)",
                        "border_color": "var(--accent-10)",
                    },
                },
            ),
        ),
        uploaded_files_list(),
        align="start",
        spacing="6",
        width="100%",
        margin_inline="auto",
        max_width="48rem",
        margin_top="2em",
    )


def home_page():
    """Home page component with file upload functionality"""
    return rx.vstack(
        rx.heading("Welcome to AI Table Analyst", size="7", margin_bottom="1em"),
        rx.text(
            "Upload your CSV or Excel files to start analyzing your data with AI-powered tools.",
            font_size="lg",
            color="var(--gray-11)",
            text_align="center",
            margin_bottom="2em",
        ),
        upload_section(),
        align="center",
        spacing="4",
        width="100%",
        padding="2em",
    )
