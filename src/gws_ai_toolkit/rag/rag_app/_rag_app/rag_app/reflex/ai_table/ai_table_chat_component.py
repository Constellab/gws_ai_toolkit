import reflex as rx

from ..chat_base.chat_config import ChatConfig
from ..chat_base.chat_input_component import chat_input_component
from ..chat_base.messages_list_component import chat_messages_list_component
from .ai_table_chat_state import AiTableChatState
from .ai_table_data_state import AiTableDataState


def ai_table_chat_component():
    chat_config = ChatConfig(
        state=AiTableChatState
    )

    return rx.box(
        rx.auto_scroll(
            chat_messages_list_component(chat_config),
            chat_input_component(chat_config),
            width="100%",
            flex="1",
            display="flex",
            min_height="0",
            class_name="ai-table-chat-component",
            flex_direction="column",
            padding="1em",
        ),

        # transition="width 0.3s ease-in-out",
        style=rx.cond(
            AiTableDataState.chat_panel_open,
            {
                "width": "600px",
                "borderLeft": "1px solid var(--gray-5)",
                "borderTop": "1px solid var(--gray-5)",
            },
            {
                "width": "0px",
            }
        ),
        overflow="hidden",
        background_color="var(--gray-2)",
        height="100%",
        class_name="ai-table-chat-panel",
        display="flex",
        border_radius="5px"
    )
