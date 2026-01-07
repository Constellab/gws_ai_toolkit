import reflex as rx
from gws_reflex_main import resource_select_button

from .ai_table.ai_table_data_state import AiTableDataState
from .ai_table.chat.table_agent.ai_table_agent_chat_config_state import AiTableAgentChatConfigState
from .main_state import MainState
from .resource_selection_state import ResourceSelectionState


def selected_tables_section():
    """Display list of uploaded files with option to select current file"""
    return rx.cond(
        AiTableDataState.dataframe_loaded,
        rx.vstack(
            rx.heading("Selected Tables", size="4"),
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
            align="center",
            margin_inline="auto",
            max_width="48rem",
            margin_top="2em",
        ),
        rx.box(),
    )


def upload_card():
    """Card component for file upload section"""
    return rx.card(
        rx.vstack(
            rx.hstack(
                rx.icon("upload", size=20, color="var(--accent-10)"),
                rx.heading("Upload Files", size="4"),
                spacing="2",
                align="center",
            ),
            rx.text(
                "Upload your CSV or Excel files to analyze.",
                color="var(--gray-11)",
                size="2",
            ),
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
                    min_height="10rem",
                ),
                rx.upload.root(
                    rx.box(
                        rx.icon(
                            tag="upload",
                            style={
                                "width": "2.5rem",
                                "height": "2.5rem",
                                "color": "var(--accent-10)",
                                "margin_bottom": "0.5rem",
                            },
                        ),
                        rx.vstack(
                            rx.text(
                                "Click to upload or drag and drop",
                                font_weight="medium",
                                color="var(--accent-10)",
                                size="2",
                            ),
                            rx.text(
                                "CSV, TSV, Excel files",
                                size="1",
                                color="var(--gray-10)",
                            ),
                            align="center",
                            spacing="1",
                        ),
                        style={
                            "display": "flex",
                            "flex_direction": "column",
                            "align_items": "center",
                            "justify_content": "center",
                            "padding": "1.5rem",
                            "text_align": "center",
                        },
                    ),
                    id="upload",
                    accept={
                        "text/csv": [".csv"],
                        "text/tab-separated-values": [".tsv"],
                        "application/vnd.ms-excel": [".xls"],
                        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet": [
                            ".xlsx"
                        ],
                    },
                    max_files=10,
                    on_drop=MainState.handle_upload(
                        rx.upload_files(on_upload_progress=MainState.handle_upload_progress)
                    ),
                    style={
                        "width": "100%",
                        "min_height": "10rem",
                        "border_width": "2px",
                        "border_style": "dashed",
                        "border_color": "var(--accent-10)",
                        "border_radius": "0.5rem",
                        "cursor": "pointer",
                        "transition_property": "all",
                        "transition_duration": "0.2s",
                        "transition_timing_function": "ease-in-out",
                        "display": "flex",
                        "align_items": "center",
                        "justify_content": "center",
                        "background_color": "var(--accent-1)",
                        "_hover": {
                            "background_color": "var(--accent-2)",
                            "border_color": "var(--accent-11)",
                        },
                    },
                ),
            ),
            spacing="3",
            width="100%",
        ),
        size="3",
        width="100%",
        height="100%",
    )


def resource_selection_card():
    """Card component for resource selection section"""
    return rx.card(
        rx.vstack(
            rx.hstack(
                rx.icon("folder-search", size=20, color="var(--accent-10)"),
                rx.heading("Lab Resources", size="4"),
                spacing="2",
                align="center",
            ),
            rx.text(
                "Choose a table resource from your lab to analyze.",
                color="var(--gray-11)",
                size="2",
            ),
            rx.box(
                resource_select_button(state=ResourceSelectionState),
                width="100%",
                display="flex",
                justify_content="center",
                padding_y="2rem",
            ),
            spacing="3",
            width="100%",
        ),
        size="3",
        width="100%",
        height="100%",
    )


def input_methods_section():
    """Section displaying upload and resource selection cards side-by-side (responsive)"""
    # Both enabled: show side by side with OR divider
    both_enabled = rx.flex(
        rx.box(upload_card(), flex="1", min_width="0", height="100%"),
        # Desktop OR text (between cards)
        rx.center(
            rx.text(
                "OR",
                font_size="xl",
                font_weight="bold",
                color="var(--gray-10)",
                padding_x="1em",
            ),
            display=["none", "none", "flex"],  # Hidden on mobile, visible on desktop
        ),
        # Mobile OR divider (between cards in vertical layout)
        rx.center(
            rx.hstack(
                rx.divider(size="4"),
                rx.text(
                    "OR",
                    font_size="lg",
                    font_weight="bold",
                    color="var(--gray-10)",
                    padding_x="1em",
                ),
                rx.divider(size="4"),
                width="100%",
                align="center",
            ),
            display=["flex", "flex", "none"],  # Visible on mobile, hidden on desktop
            width="100%",
            margin_y="1em",
        ),
        rx.box(resource_selection_card(), flex="1", min_width="0", height="100%"),
        direction=rx.breakpoints(
            initial="column", sm="row"
        ),  # Stack on mobile, side-by-side on desktop
        gap="4",
        width="100%",
        align_items="stretch",
    )

    # Only upload enabled
    upload_only = rx.box(
        upload_card(),
        width="100%",
        max_width="48rem",
        margin_inline="auto",
    )

    # Only resource selection enabled
    resource_only = rx.box(
        resource_selection_card(),
        width="100%",
        max_width="48rem",
        margin_inline="auto",
    )

    # Conditional rendering based on what's enabled
    return rx.cond(
        AiTableAgentChatConfigState.enable_file_upload
        & AiTableAgentChatConfigState.enable_resource_selection,
        both_enabled,
        rx.cond(
            AiTableAgentChatConfigState.enable_file_upload,
            upload_only,
            rx.cond(
                AiTableAgentChatConfigState.enable_resource_selection,
                resource_only,
                rx.box(),  # Neither enabled
            ),
        ),
    )


def home_page():
    """Home page component with file upload functionality"""
    return rx.vstack(
        rx.heading("Welcome to AI Table Analyst", size="7", margin_bottom="0.5em"),
        rx.text(
            "Upload files or select resources from your lab to start analyzing your data.",
            color="var(--gray-11)",
            size="3",
            text_align="center",
            margin_bottom="2em",
        ),
        input_methods_section(),
        selected_tables_section(),
        align="center",
        spacing="4",
        width="100%",
        max_width="1200px",
        margin_inline="auto",
        padding="2em",
    )
