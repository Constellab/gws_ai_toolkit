import reflex as rx

from gws_ai_toolkit._app.chat_base import (ChatConfig, chat_input_component,
                                           chat_messages_list_component,
                                           header_clear_chat_button_component)

from ...ai_table_data_state import AiTableDataState
from .ai_table_transform_agent_chat_state import AiTableTransformAgentChatState


def ai_table_transform_agent_chat_component():
    """AI Table Transform Agent chat component.

    This component provides a chat interface specifically for AI Table Transform Agent
    functionality, which generates and executes pandas code for DataFrame transformations
    based on user queries in natural language.

    Features:
        - Natural language DataFrame transformation requests
        - Real-time code generation and execution for pandas operations
        - Interactive data cleaning, filtering, and manipulation
        - Chat history and conversation management
        - Immediate DataFrame updates with transformation results

    Supported Operations:
        - Data cleaning (duplicates, missing values, data types)
        - Column operations (add, remove, rename, reorder)
        - Row operations (filter, sort, group by, aggregate)
        - Data reshaping (pivot, melt, merge, join)
        - String and datetime operations

    Returns:
        rx.Component: Complete chat interface for AI Table Transform Agent functionality
    """
    chat_config = ChatConfig(
        state=AiTableTransformAgentChatState
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
        class_name="ai-table-transform-agent-chat-component",
        flex_direction="column",
        padding="1em",
    )