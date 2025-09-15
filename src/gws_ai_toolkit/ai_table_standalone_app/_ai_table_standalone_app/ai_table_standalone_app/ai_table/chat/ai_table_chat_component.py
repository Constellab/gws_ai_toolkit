import reflex as rx

from gws_ai_toolkit._app.chat_base import (ChatConfig, chat_input_component,
                                           chat_messages_list_component,
                                           header_clear_chat_button_component)

from ..ai_table_data_state import AiTableDataState
from .ai_table_chat_state_2 import AiTableChatState2


def ai_table_chat_component():
    chat_config = ChatConfig(
        state=AiTableChatState2
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
        class_name="ai-table-chat-component",
        flex_direction="column",
        padding="1em",
    )
