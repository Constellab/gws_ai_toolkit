from collections.abc import Callable

import reflex as rx
from gws_ai_toolkit.models.chat.chat_conversation_dto import ChatConversationDTO

from ..history.history_state import HistoryState
from .chat_history_sidebar_state import ChatHistorySidebarState

ModeBadgeBuilder = Callable[[rx.Var[str]], rx.Component]


def _default_mode_badge(mode: rx.Var[str]) -> rx.Component:
    """Default mode badge using a plain Radix badge.

    :param mode: Reactive var with the conversation mode string.
    :return: A soft badge displaying the mode label.
    """
    return rx.badge(mode, size="1", variant="soft")


def _make_sidebar_conversation_item(
    mode_badge_builder: ModeBadgeBuilder,
) -> Callable[[ChatConversationDTO], rx.Component]:
    """Create a sidebar conversation item renderer with a custom mode badge builder.

    :param mode_badge_builder: Function that receives the mode var and returns a badge component.
    :return: A function suitable for use with ``rx.foreach``.
    """

    def _sidebar_conversation_item(conversation: ChatConversationDTO) -> rx.Component:
        return rx.box(
            rx.vstack(
                rx.text(
                    rx.cond(
                        conversation.label.length() > 40,
                        conversation.label[:40] + "...",
                        conversation.label,
                    ),
                    size="2",
                    font_weight="500",
                    no_of_lines=1,
                ),
                rx.hstack(
                    rx.text(
                        rx.moment(conversation.last_modified_at, from_now=True),
                        size="1",
                        color=rx.color("gray", 9),
                    ),
                    rx.spacer(),
                    mode_badge_builder(conversation.mode),
                    align="center",
                    width="100%",
                ),
                spacing="1",
                width="100%",
            ),
            padding="10px 12px",
            border_radius="8px",
            cursor="pointer",
            background_color=rx.cond(
                ChatHistorySidebarState.active_conversation_id == conversation.id,
                rx.color("accent", 3),
                "transparent",
            ),
            border_left=rx.cond(
                ChatHistorySidebarState.active_conversation_id == conversation.id,
                f"3px solid {rx.color('accent', 8)}",
                "3px solid transparent",
            ),
            _hover={
                "background_color": rx.cond(
                    ChatHistorySidebarState.active_conversation_id == conversation.id,
                    rx.color("accent", 4),
                    rx.color("gray", 3),
                ),
            },
            on_click=ChatHistorySidebarState.select_conversation(conversation.id, conversation.mode),
            width="100%",
        )

    return _sidebar_conversation_item


def chat_history_sidebar_list(
    mode_badge_builder: ModeBadgeBuilder | None = None,
) -> rx.Component:
    """Conversation history list component for use inside a sidebar.

    Displays the list of past conversations with loading and empty states.
    Does not include app branding or "New Chat" button — those should be
    added by the parent sidebar layout.

    :param mode_badge_builder: Optional callable that receives a conversation mode
        ``rx.Var[str]`` and returns a badge ``rx.Component``.  Falls back to a
        plain Radix badge when *None*.
    :return: The conversation list component.
    """
    badge_builder = mode_badge_builder or _default_mode_badge
    return rx.box(
        rx.cond(
            HistoryState.is_loading,
            rx.center(rx.spinner(size="3"), padding="20px"),
            rx.cond(
                HistoryState.has_conversations,
                rx.vstack(
                    rx.foreach(
                        HistoryState.conversations,
                        _make_sidebar_conversation_item(badge_builder),
                    ),
                    spacing="1",
                    width="100%",
                    flex="1",
                    min_height="0",
                    overflow_y="auto",
                ),
                rx.center(
                    rx.vstack(
                        rx.icon("message-circle", size=32, color=rx.color("gray", 6)),
                        rx.text(
                            "No conversations yet",
                            size="2",
                            color=rx.color("gray", 9),
                        ),
                        align="center",
                        spacing="2",
                    ),
                    padding="40px 20px",
                ),
            ),
        ),
        on_mount=HistoryState.load_conversations_if_needed,
        width="100%",
    )
