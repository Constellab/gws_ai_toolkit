import reflex as rx
from gws_ai_toolkit._app.ai_chat import (
    ChatConfig,
    chat_input_component,
    chat_messages_list_component,
    header_clear_chat_button_component,
)
from gws_ai_toolkit.models.chat.message.chat_message_dataframe import ChatMessageDataframe

from ...ai_table_data_state import AiTableDataState
from .ai_table_agent_chat_state import AiTableAgentChatState, SelectedTableDTO
from .table_selection_menu import table_selection_menu


def _dataframe_message_content(message: ChatMessageDataframe) -> rx.Component:
    """Render content for dataframe chat messages.

    Displays an optional text message followed by an interactive button/card
    that represents the generated dataframe. When clicked, switches to display
    the dataframe in the main table view.

    Args:
        message (ChatMessageDataframe): Message containing dataframe
    Returns:
        rx.Component: Rendered dataframe content with optional text and interactive button
    """
    return rx.vstack(
        # Optional text content
        rx.cond(
            message.content,
            rx.markdown(
                message.content,
                font_size="14px",
                margin_bottom="8px",
            ),
        ),
        # Interactive dataframe button
        rx.button(
            rx.hstack(
                rx.icon("table-2", size=20),
                rx.vstack(
                    rx.text(
                        rx.cond(
                            message.dataframe_name,
                            message.dataframe_name,
                            "Generated Dataframe",
                        ),
                        font_weight="600",
                        font_size="14px",
                    ),
                    rx.text(
                        "Click to view in table",
                        font_size="12px",
                        color="var(--gray-11)",
                    ),
                    spacing="0",
                    align_items="flex-start",
                ),
                spacing="3",
                align_items="center",
            ),
            on_click=AiTableDataState.switch_table(rx.cond(message.id, message.id, "")),
            variant="soft",
            size="3",
            width="100%",
            cursor="pointer",
            justify_content="start",
            height="60px",
        ),
        spacing="2",
        width="100%",
        align_items="flex-start",
    )


def ai_table_agent_chat_component():
    """AI Table Agent chat component.

    This component provides a unified chat interface for AI Table operations,
    combining both data visualization and transformation capabilities through
    intelligent function calling. The agent automatically determines whether
    to generate plots or transform data based on user requests.

    Features:
        - Unified interface for both plotting and transformation operations
        - Intelligent request routing using OpenAI function calling
        - Automatic delegation to specialized PlotlyAgentAi and TableTransformAgentAi
        - Seamless switching between visualization and transformation modes
        - Chat history and conversation management
        - Real-time updates and interactive results

    Supported Operations:
        Data Visualization:
            - Charts, graphs, and plots using Plotly
            - Statistical visualizations and dashboards
            - Interactive data exploration

        Data Transformation:
            - Data cleaning and manipulation
            - Column operations (add, remove, rename)
            - Row operations (filter, sort, aggregate)
            - Data reshaping and restructuring

    Returns:
        rx.Component: Complete chat interface for unified AI Table Agent functionality
    """
    chat_config = ChatConfig(
        state=AiTableAgentChatState,
        custom_chat_messages={  # type: ignore
            "dataframe": _dataframe_message_content,
        },
    )

    def _table_item(table: SelectedTableDTO, is_selectable: bool = False):
        """Render a table item with either remove (X) or add (+) button.

        Args:
            table: The table to render
            is_selectable: If True, shows with dashed border and + button. If False, shows as selected with X button.
        """
        return rx.box(
            rx.hstack(
                rx.icon(
                    "table-2",
                    size=16,
                    color=rx.cond(is_selectable, "var(--gray-9)", "var(--gray-10)"),
                ),
                rx.text(
                    table.unique_name,
                    font_size="12px",
                    max_width="250px",
                    overflow="hidden",
                    text_overflow="ellipsis",
                    white_space="nowrap",
                    color=rx.cond(is_selectable, "var(--gray-9)", "inherit"),
                ),
                rx.cond(
                    is_selectable,
                    rx.tooltip(
                        rx.icon(
                            "plus",
                            size=16,
                            color="var(--gray-10)",
                            cursor="pointer",
                            on_click=AiTableAgentChatState.add_table(table.id, table.sheet_name),
                        ),
                        content="Include table in chat",
                    ),
                    rx.tooltip(
                        rx.icon(
                            "x",
                            size=16,
                            color="var(--gray-10)",
                            cursor="pointer",
                            on_click=AiTableAgentChatState.remove_table(table),
                        ),
                        content="Remove table",
                    ),
                ),
                spacing="1",
                align_items="center",
            ),
            padding_x="6px",
            padding_y="2px",
            border_radius="6px",
            background=rx.cond(is_selectable, "var(--gray-2)", "var(--gray-3)"),
            border=rx.cond(is_selectable, "1px dashed var(--gray-7)", "none"),
            margin_right="6px",
            min_width="0",
            display="flex",
            align_items="center",
            user_select="none",
        )

    def _table_list():
        # Use rx.foreach to render current tables
        return rx.hstack(
            rx.foreach(
                AiTableAgentChatState.selected_tables,
                lambda table: _table_item(table, is_selectable=False),
            ),
            # Show current table selectable if it exists and is not already selected
            rx.cond(
                AiTableAgentChatState.current_table_ssuggestion,
                _table_item(AiTableAgentChatState.current_table_ssuggestion, is_selectable=True),
            ),
            table_selection_menu(),
            spacing="1",
            align_items="center",
            margin_bottom="8px",
            width="100%",
            wrap="wrap",
        )

    return rx.auto_scroll(
        rx.hstack(
            rx.heading("💬 Chat", size="3"),
            rx.spacer(),
            header_clear_chat_button_component(chat_config.state),  # type: ignore
            align_items="center",
        ),
        chat_messages_list_component(chat_config),
        _table_list(),
        chat_input_component(chat_config),
        width="100%",
        flex="1",
        display="flex",
        min_height="0",
        class_name="ai-table-table-agent-chat-component",
        flex_direction="column",
        padding="1em",
        on_mount=AiTableAgentChatState.on_load,
    )
