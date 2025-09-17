import reflex as rx

from gws_ai_toolkit._app.chat_base import (ChatConfig, chat_input_component,
                                           chat_messages_list_component,
                                           header_clear_chat_button_component)

from ...ai_table_data_state import AiTableDataState
from .ai_table_table_agent_chat_state import AiTableTableAgentChatState


def ai_table_table_agent_chat_component():
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
        state=AiTableTableAgentChatState
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
        class_name="ai-table-table-agent-chat-component",
        flex_direction="column",
        padding="1em",
    )