"""What the chat shows before the first question.

Two states, and the difference matters. With a profile selected, this is the RAG chat's own empty
screen: logo, title, input. With no profile at all, an input would be a trap — every question would be
refused for a reason the user did nothing to cause — so it points at the page that creates one instead.
"""

import reflex as rx

from ...chat_base.chat_config import ChatConfig
from ...chat_base.chat_input_component import chat_input_component
from ..chats.rag_chat_profile_list_state import CHAT_PROFILES_ROUTE
from .knowledge_base_chat_state import KnowledgeBaseChatState


def knowledge_base_empty_chat_component(config: ChatConfig) -> rx.Component:
    """The empty state of the knowledge-base chat.

    :param config: the chat configuration, for the input it renders
    """
    return rx.vstack(
        rx.box(flex="1"),
        rx.image(src="/constellab-logo.svg", width="72px", height="72px"),
        rx.heading("Knowledge base chat", size="6", weight="bold", text_align="center"),
        rx.cond(
            KnowledgeBaseChatState.has_profiles,
            _ready_to_chat(config),
            _no_profile_yet(),
        ),
        rx.box(flex="2"),
        align="center",
        width="100%",
        flex="1",
        spacing="4",
    )


def _ready_to_chat(config: ChatConfig) -> rx.Component:
    """The profile that will answer, and the input to ask it something."""
    input_children: list[rx.Component] = []
    if config.composer_extra:
        input_children.append(config.composer_extra(config.state))
    input_children.append(chat_input_component(config))

    return rx.vstack(
        rx.text(
            rx.cond(
                KnowledgeBaseChatState.selected_profile_name,
                "Ask " + KnowledgeBaseChatState.selected_profile_name + " about your documents",
                "Select a chat profile to start",
            ),
            size="3",
            color="var(--gray-11)",
            text_align="center",
            max_width="380px",
        ),
        rx.box(
            *input_children,
            width="100%",
            max_width="800px",
            margin="auto",
        ),
        align="center",
        spacing="4",
        width="100%",
    )


def _no_profile_yet() -> rx.Component:
    """No profile exists, so the only useful action is to create one."""
    return rx.vstack(
        rx.text(
            "A chat needs a chat profile: the prompt, the model and the knowledge bases it searches.",
            size="3",
            color="var(--gray-11)",
            text_align="center",
            max_width="420px",
        ),
        rx.button(
            rx.icon("plus", size=16),
            "Create a chat profile",
            on_click=rx.redirect(CHAT_PROFILES_ROUTE),
        ),
        align="center",
        spacing="4",
    )
