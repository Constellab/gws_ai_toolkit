from typing import List

import reflex as rx

from ...reflex.ai_expert.ai_expert_state import AiExpertState
from ..chat_base.chat_component import chat_component
from ..chat_base.chat_config import ChatConfig
from ..chat_base.chat_header_component import \
    header_clear_chat_button_component
from ..chat_base.chat_state_base import ChatStateBase


def ai_expert_header_default_buttons_component(state: ChatStateBase) -> List[rx.Component]:
    """Header buttons for the AI Expert page."""
    return [
        rx.button(
            rx.icon('file', size=16),
            "View document",
            on_click=lambda: AiExpertState.open_current_resource_doc,
            variant='outline',
            cursor="pointer",
            size="2",
        ),
        header_clear_chat_button_component(state)
    ]


def ai_expert_component(chat_config: ChatConfig | None = None) -> rx.Component:
    """
    Call AI expert full component.

    Args:
        chat_config (ChatConfig | None, optional): Custom ChatConfig to override the defaults. Defaults to None.

    Returns:
        rx.Component: The AI expert component.
    """
    if not chat_config:
        config = ChatConfig(
            state=AiExpertState,
            header_buttons=ai_expert_header_default_buttons_component
        )

    return chat_component(config)
