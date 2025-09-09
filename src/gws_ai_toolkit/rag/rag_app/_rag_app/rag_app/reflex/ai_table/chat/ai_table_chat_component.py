import reflex as rx

from ...chat_base.chat_config import ChatConfig
from ...chat_base.chat_header_component import \
    header_clear_chat_button_component
from ...chat_base.chat_input_component import chat_input_component
from ...chat_base.messages_list_component import chat_messages_list_component
from ..ai_table_data_state import AiTableDataState
from .ai_table_chat_state import AiTableChatState


def ai_table_chat_component():
    chat_config = ChatConfig(
        state=AiTableChatState
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
