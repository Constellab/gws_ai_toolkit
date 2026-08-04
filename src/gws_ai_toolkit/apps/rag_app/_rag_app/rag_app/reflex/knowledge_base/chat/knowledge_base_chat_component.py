"""The knowledge-base chat window: the shared chat widget, wired to a chat profile.

Almost nothing is drawn here. The message list, the streaming indicator, the input and the source
dialog are the shared ``chat_base`` widget the RAG chat and the AI Expert already use; what this
module adds is the three things specific to a knowledge-base chat:

- a **header** carrying the profile selector, since the profile is what decides how the chat answers;
- a **source menu** offering only *Open document*, because a source here points at a knowledge-base
  document rather than at a lab resource an AI Expert could be opened on (see issue #14);
- a **read-only view** for a conversation that cannot be continued — a legacy ``rag`` row, or one
  whose profile was deleted. Its transcript is rendered without an input, above the reason. Reusing
  ``chat_component`` there would have put a working input under a conversation nothing can answer for.
"""

import reflex as rx
from gws_ai_toolkit.models.chat.message.chat_message_source import (
    ChatMessageSourceFront,
    RagChatSourceFront,
)
from gws_reflex_main import left_sidebar_open_button

from ...chat_base.chat_component import chat_component
from ...chat_base.chat_config import ChatConfig
from ...chat_base.conversation_chat_state_base import ConversationChatStateBase
from ...chat_base.messages_list_component import chat_messages_list_component
from ...chat_base.source.source_message_component import (
    custom_sources_list_component,
    source_message_component,
)
from ..chats.rag_chat_profile_list_state import CHAT_PROFILES_ROUTE
from .knowledge_base_chat_state import ChatProfileOption, KnowledgeBaseChatState
from .knowledge_base_empty_chat_component import knowledge_base_empty_chat_component


def knowledge_base_source_menu_items(
    source: RagChatSourceFront, state: ConversationChatStateBase
) -> list[rx.Component]:
    """Actions offered on a source pill: open the document it came from.

    Deliberately shorter than the default menu: *Open AI Expert* is dropped because AI Expert still
    runs against the retired datasets, so it could not open a knowledge-base document.

    :param source: the clicked source
    :param state: the chat state handling the action
    """
    return [
        rx.menu.item(
            rx.icon("external-link", size=16),
            "Open document",
            on_click=lambda: state.open_document(source.document_id),
        ),
    ]


def knowledge_base_chat_config_factory() -> ChatConfig:
    """The chat configuration of the knowledge-base window.

    :return: the configuration handed to the shared chat widget
    """
    sources_component_builder = custom_sources_list_component(knowledge_base_source_menu_items)

    return ChatConfig(
        state=KnowledgeBaseChatState,
        header=knowledge_base_chat_header_component(),
        custom_chat_messages={
            "source": (
                ChatMessageSourceFront,
                lambda message: source_message_component(
                    message, KnowledgeBaseChatState, sources_component_builder
                ),
            ),
        },
    )


def knowledge_base_chat_component(chat_config: ChatConfig | None = None) -> rx.Component:
    """The knowledge-base chat window.

    :param chat_config: a configuration overriding the default, for an app that customises the chat
    :return: the chat window, or the read-only transcript when the conversation cannot be continued
    """
    config = chat_config or knowledge_base_chat_config_factory()

    return rx.cond(
        KnowledgeBaseChatState.is_read_only,
        _read_only_transcript(config),
        chat_component(config, empty_chat_component=knowledge_base_empty_chat_component),
    )


def knowledge_base_chat_header_component() -> rx.Component:
    """Header of the chat: the sidebar toggle, the profile selector, and the way to edit profiles."""
    return rx.hstack(
        left_sidebar_open_button(),
        rx.icon("database", size=16, color="var(--gray-9)"),
        _profile_selector(),
        rx.spacer(),
        rx.tooltip(
            rx.button(
                rx.icon("settings", size=16),
                variant="ghost",
                size="2",
                cursor="pointer",
                color_scheme="gray",
                on_click=rx.redirect(CHAT_PROFILES_ROUTE),
            ),
            content="Chat profiles",
        ),
        align="center",
        spacing="3",
        width="100%",
    )


def _profile_selector() -> rx.Component:
    """Which profile answers. Empty until one exists, which is a state the page explains elsewhere."""
    return rx.cond(
        KnowledgeBaseChatState.has_profiles,
        rx.select.root(
            rx.select.trigger(placeholder="Select a chat profile", variant="soft"),
            rx.select.content(
                rx.foreach(KnowledgeBaseChatState.profile_options, _profile_select_item),
            ),
            value=KnowledgeBaseChatState.selected_profile_id,
            on_change=KnowledgeBaseChatState.select_profile,
        ),
        rx.link(
            rx.text("No chat profile yet — create one", size="2"),
            href=CHAT_PROFILES_ROUTE,
        ),
    )


def _profile_select_item(profile: ChatProfileOption) -> rx.Component:
    """One selectable profile."""
    return rx.select.item(profile.name, value=profile.id)


def _read_only_transcript(config: ChatConfig) -> rx.Component:
    """A conversation that can be read but not continued, and the reason why."""
    return rx.box(
        rx.box(knowledge_base_chat_header_component(), padding_bottom="1em"),
        _read_only_notice(),
        chat_messages_list_component(config),
        width="100%",
        max_width="800px",
        margin="0 auto",
        display="flex",
        flex_direction="column",
        flex="1",
        min_height="0",
        overflow_y="auto",
    )


def _read_only_notice() -> rx.Component:
    """Why this conversation has no input, said in the words the restore path reported."""
    return rx.hstack(
        rx.icon("info", size=16, color="var(--gray-11)", flex_shrink="0"),
        rx.vstack(
            rx.text(KnowledgeBaseChatState.read_only_notice, size="2"),
            rx.button(
                rx.icon("plus", size=14),
                "Start a new chat",
                variant="soft",
                size="1",
                on_click=KnowledgeBaseChatState.start_new_chat,
            ),
            spacing="2",
            align="start",
        ),
        align="start",
        spacing="2",
        padding="12px",
        border_radius="8px",
        background="var(--gray-3)",
        border_left="4px solid var(--gray-8)",
        width="100%",
        margin_bottom="1em",
    )
