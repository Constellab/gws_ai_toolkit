import reflex as rx
from gws_reflex_main import dialog_header, resource_select_button, sidebar_header_component
from reflex_resizable_panels import resizable_panels as rzp

from ..main_state import MainState
from ..resource_selection_state import ResourceSelectionState
from .ai_table_data_state import AiTableDataState
from .ai_table_section import table_section
from .chat.table_agent.ai_table_agent_chat_component import ai_table_agent_chat_component
from .chat.table_agent.ai_table_agent_chat_config_state import AiTableAgentChatConfigState
from .stats.ai_table_stats_component import ai_table_stats_component


def _table_selector():
    """Select dropdown for switching between tables (no remove button)"""
    return rx.cond(
        AiTableDataState.excel_file_list,  # Only show if there are tables
        rx.select.root(
            rx.select.trigger(
                placeholder="Select table",
            ),
            rx.select.content(
                rx.foreach(
                    AiTableDataState.excel_file_list,
                    lambda table: rx.select.item(
                        rx.text(table["name"]),
                        value=table["id"],
                    ),
                ),
            ),
            value=AiTableDataState.current_table_id,
            on_change=AiTableDataState.select_excel_file,
            size="2",
        ),
        rx.box(),  # Empty box when no tables
    )


def _sheet_selector():
    """Select dropdown for switching between sheets"""
    return rx.cond(
        AiTableDataState.has_multiple_sheets,
        rx.select.root(
            rx.select.trigger(
                placeholder="Select sheet",
            ),
            rx.select.content(
                rx.foreach(
                    AiTableDataState.get_sheet_names,
                    lambda sheet: rx.select.item(
                        sheet,
                        value=sheet,
                    ),
                ),
            ),
            value=AiTableDataState.current_sheet_name,
            on_change=AiTableDataState.switch_sheet,
            size="2",
        ),
    )


def _import_dialog_upload_card():
    """Upload card for the import dialog"""
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
                    id="import_dialog_upload",
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
                        rx.upload_files(
                            upload_id="import_dialog_upload",
                            on_upload_progress=MainState.handle_upload_progress,
                        )
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
    )


def _import_dialog_resource_card():
    """Resource selection card for the import dialog"""
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
    )


def _import_dialog_uploaded_list():
    """List of already uploaded tables inside the import dialog"""
    return rx.cond(
        AiTableDataState.excel_file_list,
        rx.vstack(
            rx.heading("Uploaded Tables", size="4"),
            rx.vstack(
                rx.foreach(
                    AiTableDataState.excel_file_list,
                    lambda table: rx.hstack(
                        rx.icon("table", size=16, color="var(--accent-9)"),
                        rx.text(table["name"], font_weight="medium", size="2"),
                        rx.spacer(),
                        rx.button(
                            "Open",
                            size="1",
                            variant="outline",
                            on_click=[
                                AiTableDataState.select_excel_file(table["id"]),
                                AiTableDataState.set_import_dialog_open(False),
                            ],
                        ),
                        align="center",
                        width="100%",
                        padding="0.5em 0.75em",
                        border="1px solid var(--gray-4)",
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


def _import_dialog():
    """Dialog with upload, resource selection, and uploaded files list"""
    # Build the input methods section based on config flags
    both_enabled = rx.flex(
        rx.box(_import_dialog_upload_card(), flex="1", min_width="0"),
        rx.center(
            rx.text(
                "OR",
                font_size="xl",
                font_weight="bold",
                color="var(--gray-10)",
                padding_x="1em",
            ),
        ),
        rx.box(_import_dialog_resource_card(), flex="1", min_width="0"),
        direction="row",
        gap="4",
        width="100%",
        align_items="stretch",
    )

    upload_only = rx.box(_import_dialog_upload_card(), width="100%")
    resource_only = rx.box(_import_dialog_resource_card(), width="100%")

    input_section = rx.cond(
        AiTableAgentChatConfigState.enable_file_upload
        & AiTableAgentChatConfigState.enable_resource_selection,
        both_enabled,
        rx.cond(
            AiTableAgentChatConfigState.enable_file_upload,
            upload_only,
            rx.cond(
                AiTableAgentChatConfigState.enable_resource_selection,
                resource_only,
                rx.box(),
            ),
        ),
    )

    return rx.dialog.root(
        rx.dialog.content(
            dialog_header(
                title=rx.hstack(
                    rx.icon("import", size=20),
                    rx.text("Import Data", weight="bold", size="4"),
                    spacing="2",
                    align="center",
                ),
                close=AiTableDataState.set_import_dialog_open(False),
            ),
            rx.dialog.description(
                "Upload files or select resources from your lab.",
                size="2",
                color="var(--gray-11)",
                margin_bottom="1em",
            ),
            rx.vstack(
                input_section,
                _import_dialog_uploaded_list(),
                spacing="4",
                width="100%",
            ),
            max_width="1000px",
            width="90vw",
        ),
        open=AiTableDataState.import_dialog_open,
        on_open_change=AiTableDataState.set_import_dialog_open,
    )


def _table_header(header_left_component: rx.Component | None = None):
    """Header component for the AI Table view.

    Layout: Title | File selector | Sheet selector | Import button | --- spacer --- | Chat button | Stats button
    """
    return rx.hstack(
        *([header_left_component] if header_left_component is not None else []),
        sidebar_header_component(
            title="Analytics",
            subtitle="By Constellab",
            logo_src="/constellab-logo.svg",
            padding="0",
        ),
        rx.separator(orientation="vertical", size="4", height="70%"),
        # File/table selector
        _table_selector(),
        # Sheet selector
        _sheet_selector(),
        # Import button
        rx.separator(orientation="vertical", size="4", height="70%"),
        rx.button(
            rx.icon("plus", size=14),
            "Import",
            variant="outline",
            size="2",
            on_click=AiTableDataState.set_import_dialog_open(True),
        ),
        _import_dialog(),
        rx.spacer(),
        # Panel toggle buttons on the right (styled via CSS classes)
        rx.button(
            rx.icon("message-circle", size=14),
            "Chat",
            on_click=lambda: AiTableDataState.toggle_right_panel_state("chat"),
            variant="solid",
            size="2",
            class_name=rx.cond(
                AiTableDataState.right_panel_state == "chat",
                "toggle-btn-secondary active",
                "toggle-btn-secondary",
            ),
        ),
        rx.button(
            rx.icon("bar-chart-3", size=14),
            "Stats",
            on_click=lambda: AiTableDataState.toggle_right_panel_state("stats"),
            variant="ghost",
            size="2",
            class_name=rx.cond(
                AiTableDataState.right_panel_state == "stats",
                "toggle-btn-accent active",
                "toggle-btn-accent",
            ),
        ),
        rx.cond(
            AiTableDataState.show_config_page,
            rx.button(
                rx.icon("settings", size=14),
                "Settings",
                on_click=rx.redirect("/config"),
                variant="ghost",
                size="2",
                margin_left="1em",
            ),
        ),
        align_items="center",
        width="100%",
        padding="0.5em 2em 0.5em 1em",
        spacing="4",
        border_bottom="1px solid var(--gray-4)",
        background="var(--color-background)",
    )


def _right_panel() -> rx.Component:
    return rx.box(
        rx.match(
            AiTableDataState.right_panel_state,
            ("chat", ai_table_agent_chat_component()),
            ("stats", ai_table_stats_component()),
        ),
        background_color="var(--color-background)",
        border_left="1px solid var(--gray-4)",
        height="100%",
        display="flex",
        border_radius="5px",
        width="100%",
    )


def ai_table_layout(header_left_component: rx.Component | None = None):
    """Main AI Table layout with collapsible chat panel"""
    return rx.vstack(
        # Header
        _table_header(header_left_component),
        rzp.group(
            rzp.panel(
                # Table section (flexible width)
                table_section(),
                default_size=70,
                min_size=10,
                order=1,
            ),
            rx.cond(
                AiTableDataState.right_panel_opened,
                rx.fragment(
                    rzp.handle(background="initial", width="1px"),
                    rzp.panel(_right_panel(), default_size=30, min_size=10, order=2),
                ),
            ),
            direction="horizontal",
            width="100%",
            flex="1",
            min_height="0",
        ),
        # Main content area
        # rx.hstack(
        #     # Table section (flexible width)
        #     table_section(),
        #     # Chat panel (collapsible)
        #     ai_table_chat_component(),
        #     spacing="0",
        #     width="100%",
        #     flex="1",
        #     min_height="0",
        # ),
        width="100%",
        height="100%",
        spacing="0",
    )


def ai_table_component(header_left_component: rx.Component | None = None) -> rx.Component:
    """AI Table component with integrated table view and chat functionality.

    This component provides a comprehensive data analysis interface that combines:
    - Rich table visualization with AG Grid
    - Collapsible AI chat panel for data analysis conversations
    - Sheet selection for Excel files
    - File loading from resources (URL-based)

    Features:
        - Excel/CSV data visualization with sorting and filtering
        - AI-powered data analysis chat with code interpreter
        - Multi-sheet support for Excel files
        - Responsive layout with collapsible chat panel
        - Streaming responses with code execution visualization

    Args:
        header_left_component: Optional component to display before the title in the header.

    The component uses two main states:
        - AiTableDataState: Manages dataframe loading, table display, and UI state
        - AiTableChatState: Handles AI chat interactions and OpenAI integration

    Returns:
        rx.Component: Complete AI Table interface with table and chat functionality
    """
    return rx.cond(
        AiTableDataState.dataframe_loaded,
        # Show full table interface when dataframe is loaded
        ai_table_layout(header_left_component),
        # Show loading state when no dataframe
        rx.center(
            rx.hstack(
                rx.spinner(size="3"),
                rx.text("Loading data...", font_size="lg"),
                spacing="4",
            ),
            height="100%",
            width="100%",
        ),
    )
