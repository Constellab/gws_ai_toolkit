import reflex as rx

from gws_ai_toolkit._app.chat_base import (ChatConfig, chat_input_component,
                                           chat_messages_list_component,
                                           header_clear_chat_button_component)

from ...ai_table_data_state import AiTableDataState
from .ai_table_plot_agent_chat_state import AiTablePlotAgentChatState


def ai_table_plot_agent_chat_component():
    """AI Table Plot Agent chat component.

    This component provides a chat interface specifically for AI Table Plot Agent
    functionality, which generates Python code for Plotly visualizations based on
    table metadata and user queries.

    Features:
        - Metadata-based analysis with code generation
        - Interactive Plotly visualizations through generated code
        - Local code execution for data visualization
        - Chat history and conversation management

    Returns:
        rx.Component: Complete chat interface for AI Table Plot Agent functionality
    """
    chat_config = ChatConfig(
        state=AiTablePlotAgentChatState
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
        class_name="ai-table-plot-agent-chat-component",
        flex_direction="column",
        padding="1em",
    )