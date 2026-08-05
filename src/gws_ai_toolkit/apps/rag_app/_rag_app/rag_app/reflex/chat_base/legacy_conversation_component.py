"""The read-only view for a conversation whose mode is retired.

Any :class:`~gws_ai_toolkit.models.chat.conversation.base_chat_conversation.ChatConversationMode`
that becomes ``is_legacy`` opens here instead of its own live chat: the messages are still readable
through the standard renderer, but there is no input, because nothing on the retired mode's side of
the conversation is left to answer with. ``RAG`` was the first mode retired into this state; any mode
retired later (see ``ChatConversationMode.is_legacy``) reuses this exact view rather than growing a
dedicated one.
"""

import reflex as rx
from gws_ai_toolkit.models.chat.conversation.base_chat_conversation import (
    LEGACY_CONVERSATION_MODE_MESSAGE,
)

from .chat_config import ChatConfig
from .messages_list_component import chat_messages_list_component


def legacy_conversation_component(
    config: ChatConfig, extra_actions: rx.Component | None = None
) -> rx.Component:
    """Read-only transcript of a legacy conversation, with the one message every retired mode shares.

    :param config: chat configuration; its header and messages are used, its composer never is
    :param extra_actions: page-specific actions to offer alongside the notice (e.g. a "start a new
            chat" button), since where that should lead differs per page
    :return: the header (if any), the retirement notice, and the transcript — no input
    """
    header = [rx.box(config.header, padding_bottom="1em")] if config.header is not None else []

    return rx.box(
        *header,
        _legacy_conversation_notice(extra_actions),
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


def _legacy_conversation_notice(extra_actions: rx.Component | None) -> rx.Component:
    """Why this conversation has no input: the generic message every retired mode shares."""
    content = [rx.text(LEGACY_CONVERSATION_MODE_MESSAGE, size="2")]
    if extra_actions is not None:
        content.append(extra_actions)

    return rx.hstack(
        rx.icon("info", size=16, color="var(--gray-11)", flex_shrink="0"),
        rx.vstack(
            *content,
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
