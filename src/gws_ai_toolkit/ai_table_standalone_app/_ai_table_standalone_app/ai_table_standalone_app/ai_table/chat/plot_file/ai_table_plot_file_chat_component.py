import reflex as rx

from gws_ai_toolkit._app.ai_rag import (ChatConfig, chat_input_component,
                                        chat_messages_list_component,
                                        header_clear_chat_button_component)

from ...ai_table_data_state import AiTableDataState
from .ai_table_plot_file_chat_state import AiTablePlotFileChatState


def ai_table_plot_file_chat_component():
    """AI Table Plot File chat component.

    This component provides a chat interface specifically for AI Table Plot File
    functionality, which uploads the entire Excel/CSV file to OpenAI for analysis
    with code interpreter capabilities.

    Features:
        - File-based analysis with full data access
        - Interactive Plotly visualizations through function calls
        - Comprehensive data analysis with pandas
        - Chat history and conversation management

    Returns:
        rx.Component: Complete chat interface for AI Table Plot File functionality
    """
    chat_config = ChatConfig(
        state=AiTablePlotFileChatState
    )

    return rx.auto_scroll(
        rx.hstack(
            rx.heading(AiTableDataState.current_table_name, size="3"),
            rx.spacer(),
            header_clear_chat_button_component(chat_config.state),
            align_items="center",
        ),
        chat_messages_list_component(chat_config),
        chat_input_component(chat_config),
        width="100%",
        flex="1",
        display="flex",
        min_height="0",
        class_name="ai-table-plot-file-chat-component",
        flex_direction="column",
        padding="1em",
    )
