
import reflex as rx
from reflex_resizable_panels import resizable_panels as rzp

from .ai_table_data_state import AiTableDataState
from .ai_table_section import table_section
from .chat.plot_agent.ai_table_plot_agent_chat_component import ai_table_plot_agent_chat_component as ai_table_chat_component
from .stats.ai_table_stats_component import ai_table_stats_component


def table_selector():
    """Select dropdown for switching between original table and subtables"""
    return rx.cond(
        AiTableDataState.subtables_list,  # Only show if there are subtables
        rx.hstack(
            rx.text("Table:", font_weight="bold"),
            rx.select.root(
                rx.select.trigger(
                    placeholder="Select table",
                ),
                rx.select.content(
                    # Original table option
                    rx.select.item(
                        "📊 Original Table",
                        value="original",
                    ),
                    # Subtable options - iterate over subtables list
                    rx.foreach(
                        AiTableDataState.subtables_list,
                        lambda subtable: rx.select.item(
                            rx.text("📋 ", subtable["name"]),
                            value=subtable["id"],
                        ),
                    ),
                ),
                value=AiTableDataState.current_table_id,
                on_change=AiTableDataState.switch_table,
            ),
            # Remove button for current subtable (only show if subtable is selected)
            rx.cond(
                AiTableDataState.current_table_id != "original",
                rx.button(
                    "❌ Remove",
                    variant="outline",
                    color_scheme="red",
                    on_click=AiTableDataState.remove_subtable(AiTableDataState.current_table_id),
                    size="2",
                ),
                rx.box(),
            ),
            spacing="2",
            align="center",
        ),
        rx.box()  # Empty box when no tables
    )


def _table_header():
    """Header component for the AI Table view"""
    return rx.hstack(
        rx.heading("AI Table Analyst", size="6"),
        rx.spacer(),
        rx.cond(
            AiTableDataState.has_multiple_sheets,  # Only show for original table
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
        # Table selector (only when subtables exist)
        table_selector(),
        rx.button(
            "💬 Chat",
            on_click=lambda: AiTableDataState.toggle_right_panel_state('chat'),
            variant="solid",
            cursor="pointer",
        ),
        rx.button(
            "📈 Stats",
            on_click=lambda: AiTableDataState.toggle_right_panel_state('stats'),
            variant="solid",
            cursor="pointer",
        ),
        align_items="center",
        width="100%",
        padding="0.5em 1em",
        spacing="4",
    )


def _right_panel() -> rx.Component:
    return rx.box(
        rx.match(
            AiTableDataState.right_panel_state,
            ("chat", ai_table_chat_component()),
            ("stats", ai_table_stats_component()),
        ),
        background_color="var(--gray-2)",
        height="100%",
        display="flex",
        border_radius="5px",
        width="100%",
    )


def ai_table_layout():
    """Main AI Table layout with collapsible chat panel"""
    return rx.vstack(
        # Header
        _table_header(),

        rzp.group(
            rzp.panel(
                # Table section (flexible width)
                table_section(),
                default_size=70,
                min_size=10,
                order=1
            ),
            rx.cond(
                AiTableDataState.right_panel_opened,
                rx.fragment(
                    rzp.handle(
                        background="initial",
                        width="1px"
                    ),
                    rzp.panel(
                        _right_panel(),
                        default_size=30,
                        min_size=10,
                        order=2
                    ),
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
