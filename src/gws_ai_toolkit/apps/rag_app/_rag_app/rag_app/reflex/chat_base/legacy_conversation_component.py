"""The read-only view for a conversation that cannot be continued, and the reason why.

Two levels live here:

- :func:`unavailable_conversation_component` and :func:`conversation_notice` are the shared shell —
  a scrollable read-only transcript with a notice above it — for *any* reason a conversation cannot
  be continued, generic or mode-specific. ``knowledge_base_chat_component`` reuses them for its own
  knowledge-base-specific reasons (wrong mode, no profile, deleted profile) instead of duplicating
  the layout.
- :func:`legacy_conversation_component` is the one built on top of it for the single generic reason
  every retired mode shares: a conversation whose
  :class:`~gws_ai_toolkit.models.chat.conversation.base_chat_conversation.ChatConversationMode` is
  ``is_legacy``. ``RAG`` was the first mode retired into this state; any mode retired later reuses
  this exact view rather than growing a dedicated one.
"""

import reflex as rx
from gws_ai_toolkit.models.chat.conversation.base_chat_conversation import (
    LEGACY_CONVERSATION_MODE_MESSAGE,
)

from .chat_config import ChatConfig
from .messages_list_component import chat_messages_list_component


def unavailable_conversation_component(config: ChatConfig, notice: rx.Component) -> rx.Component:
    """A conversation read but not continued: its header (if any), a `notice`, and its transcript.

    :param config: chat configuration; its header and messages are used, its composer never is
    :param notice: why there is no input — built by :func:`conversation_notice`
    :return: the header (if any), the notice, and the transcript — no input
    """
    header = [rx.box(config.header, padding_bottom="1em")] if config.header is not None else []

    return rx.box(
        *header,
        notice,
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


def conversation_notice(content: rx.Component | list[rx.Component]) -> rx.Component:
    """The info-icon box every "cannot be continued" reason is said through.

    :param content: the message (and any actions below it) to show; a single component or a list
    """
    items = content if isinstance(content, list) else [content]

    return rx.hstack(
        rx.icon("info", size=16, color="var(--gray-11)", flex_shrink="0"),
        rx.vstack(
            *items,
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


def legacy_conversation_component(
    config: ChatConfig, extra_actions: rx.Component | None = None
) -> rx.Component:
    """Read-only transcript of a legacy conversation, with the one message every retired mode shares.

    :param config: chat configuration; its header and messages are used, its composer never is
    :param extra_actions: page-specific actions to offer alongside the notice (e.g. a "start a new
            chat" button), since where that should lead differs per page
    :return: the header (if any), the retirement notice, and the transcript — no input
    """
    content = [rx.text(LEGACY_CONVERSATION_MODE_MESSAGE, size="2")]
    if extra_actions is not None:
        content.append(extra_actions)

    return unavailable_conversation_component(config, conversation_notice(content))
