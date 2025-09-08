
import reflex as rx

from .ai_table_chat_component import ai_table_chat_component
from .ai_table_data_state import AiTableDataState
from .table_section import table_section


def table_header():
    """Header component for the AI Table view"""
    return rx.hstack(
        rx.heading("AI Table Analyst", size="6"),
        rx.spacer(),
        rx.cond(
            AiTableDataState.has_multiple_sheets,
            rx.hstack(
                rx.text("Sheet:", font_weight="bold"),
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
                ),
                spacing="2",
                align="center",
            ),
            rx.text("")
        ),
        rx.button(
            rx.cond(
                AiTableDataState.chat_panel_open,
                "Hide Chat",
                "💬 Show Chat"
            ),
            on_click=AiTableDataState.toggle_chat_panel,
            variant="solid",
            color_scheme="blue",
        ),
        align_items="center",
        width="100%",
        padding="0.5em 1em",
    )


def ai_table_layout():
    """Main AI Table layout with collapsible chat panel"""
    return rx.vstack(
        # Header
        table_header(),

        # Main content area
        rx.hstack(
            # Table section (flexible width)
            table_section(),

            # Chat panel (collapsible)
            ai_table_chat_component(),

            spacing="0",
            width="100%",
            flex="1",
            min_height="0",
        ),
        width="100%",
        spacing="0"
    )


def ai_table_component() -> rx.Component:
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

    The component uses two main states:
        - AiTableDataState: Manages dataframe loading, table display, and UI state
        - AiTableChatState: Handles AI chat interactions and OpenAI integration

    Returns:
        rx.Component: Complete AI Table interface with table and chat functionality
    """
    return rx.cond(
        AiTableDataState.dataframe_loaded,
        # Show full table interface when dataframe is loaded
        ai_table_layout(),
        # Show loading state when no dataframe
        rx.center(
            rx.hstack(
                rx.spinner(size="3"),
                rx.text("Loading data...", font_size="lg"),
                spacing="4",
            ),
            height="100%",
            width="100%",
        )
    )
