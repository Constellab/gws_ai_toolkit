import reflex as rx

from .main_state import MainState


def upload_section():
    """Component for file upload section"""
    return rx.vstack(
        rx.heading("Upload your CSV or Excel file"),
        rx.upload.root(
            rx.box(
                rx.icon(
                    tag="upload",
                    style={"width": "3rem", "height": "3rem", "color": "var(--accent-10)", "margin_bottom": "0.75rem"},),
                rx.vstack(
                    rx.hstack(
                        rx.text("Click to upload", style={"font_weight": "bold", "color": "var(--accent-10)"},),
                        rx.text(" or drag and drop", style={"color": "var(--gray-10)"}),
                        spacing="1",),
                    rx.text(
                        "CSV, Excel files (.csv, .xls, .xlsx)",
                        style={"font_size": "0.875rem", "color": "var(--gray-10)", "margin_top": "0.25rem"},),
                    align="center", spacing="1",),
                style={"display": "flex", "flex_direction": "column", "align_items": "center",
                       "justify_content": "center", "padding": "2rem", "text_align": "center", },),
            id="upload",
            accept={"text/csv": [".csv"],
                    "application/vnd.ms-excel": [".xls"],
                    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet": [".xlsx"]},
            max_files=1, on_drop=MainState.handle_upload(rx.upload_files("upload")),
            style={"width": "100%", "height": "12rem", "border_width": "2px", "border_style": "dashed",
                   "border_color": "var(--accent-10)", "border_radius": "0.75rem", "cursor": "pointer",
                   "transition_property": "all", "transition_duration": "0.2s",
                   "transition_timing_function": "ease-in-out", "display": "flex", "align_items": "center",
                   "justify_content": "center", "background_color": "white",
                   "_hover": {"background_color": "var(--accent-2)", "border_color": "var(--accent-10)", }, },),
        align="start", spacing="3",  width="100%", margin_inline="auto", max_width="48rem", margin_top="1em",)
