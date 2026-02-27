from collections.abc import Callable

import reflex as rx
from gws_ai_toolkit.models.chat.chat_conversation_dto import ChatConversationDTO

from ..chat_base.chat_config import ChatConfig
from ..chat_base.messages_list_component import (
    source_message_component,
)
from ..chat_base.source.source_message_component import SourcesComponentBuilder
from ..read_only_chat.read_only_chat_interface import read_only_chat_component
from ..read_only_chat.read_only_chat_state import ReadOnlyChatState
from .history_config_dialog import history_config_dialog
from .history_state import HistoryState

ModeBadgeBuilder = Callable[[rx.Var[str]], rx.Component]


def _default_mode_badge(mode: rx.Var[str]) -> rx.Component:
    """Default mode badge using a plain Radix badge.

    :param mode: Reactive var with the conversation mode string.
    :return: A soft badge displaying the mode label.
    """
    mode_display = mode.replace("_", " ").title()
    return rx.badge(mode_display, size="1", variant="soft")


def _make_conversation_item(
    mode_badge_builder: ModeBadgeBuilder,
) -> Callable[[ChatConversationDTO], rx.Component]:
    """Create a conversation item renderer with a custom mode badge builder.

    :param mode_badge_builder: Function that receives the mode var and returns a badge component.
    :return: A function suitable for use with ``rx.foreach``.
    """

    def _conversation_item(conversation: ChatConversationDTO) -> rx.Component:
        return rx.box(
            rx.vstack(
                rx.hstack(
                    rx.heading(
                        rx.cond(
                            conversation.label.length() > 60,
                            conversation.label[:60] + "...",
                            conversation.label,
                        ),
                        size="3",
                        margin_bottom="4px",
                        font_weight="600",
                    ),
                    rx.spacer(),
                    width="100%",
                ),
                rx.hstack(
                    mode_badge_builder(conversation.mode),
                    rx.spacer(),
                    rx.text(
                        rx.moment(conversation.last_modified_at, format="MMM D, YYYY h:mm"),
                        size="2",
                        color=rx.color("gray", 11),
                    ),
                    spacing="2",
                    align_items="center",
                    width="100%",
                ),
                spacing="1",
                align_items="start",
                width="100%",
            ),
            padding="12px 16px",
            border_radius="8px",
            cursor="pointer",
            border=rx.cond(
                HistoryState.selected_conversation_id == conversation.id,
                f"2px solid {rx.color('accent', 8)}",
                f"1px solid {rx.color('gray', 6)}",
            ),
            background_color=rx.cond(
                HistoryState.selected_conversation_id == conversation.id, rx.color("accent", 3), "white"
            ),
            _hover={
                "background_color": rx.cond(
                    HistoryState.selected_conversation_id == conversation.id,
                    rx.color("accent", 4),
                    rx.color("gray", 2),
                ),
            },
            on_click=lambda: HistoryState.select_conversation(conversation.id),
            margin_bottom="8px",
            width="100%",
        )

    return _conversation_item


def _conversations_sidebar(mode_badge_builder: ModeBadgeBuilder) -> rx.Component:
    """Left sidebar with conversation list.

    :param mode_badge_builder: Function that receives the mode var and returns a badge component.
    """
    return rx.box(
        rx.vstack(
            rx.hstack(
                rx.heading("Conversation History", size="4", font_weight="600"),
                rx.spacer(),
                rx.button(
                    rx.icon("refresh-cw", size=16),
                    variant="ghost",
                    size="2",
                    on_click=HistoryState.load_conversations,
                ),
                width="100%",
                align_items="center",
                margin_bottom="1em",
                padding_inline="1em",
            ),
            # Loading state
            rx.cond(
                HistoryState.is_loading,
                rx.box(
                    rx.spinner(size="3"),
                    rx.text("Loading conversations...", size="2", color=rx.color("gray", 11)),
                    padding="20px",
                    text_align="center",
                ),
                # Content when not loading
                rx.cond(
                    HistoryState.has_conversations,
                    # Show conversations list
                    rx.vstack(
                        rx.foreach(
                            HistoryState.conversations,
                            _make_conversation_item(mode_badge_builder),
                        ),
                        spacing="0",
                        width="100%",
                        padding_inline="1em",
                        # max height 100% with scroll
                        flex="1",
                        min_height="0",
                        overflow_y="auto",
                    ),
                    # Show empty state
                    rx.box(
                        rx.icon("message-circle", size=48, color=rx.color("gray", 6)),
                        rx.heading("No Conversations", size="4", margin_top="16px"),
                        rx.text(
                            "Start chatting to see your conversation history here.",
                            size="2",
                            color=rx.color("gray", 11),
                            text_align="center",
                            margin_top="8px",
                        ),
                        display="flex",
                        flex_direction="column",
                        align_items="center",
                        justify_content="center",
                        padding="40px 20px",
                        text_align="center",
                    ),
                ),
            ),
            spacing="0",
            width="100%",
            height="100%",
        ),
        width="350px",
        height="100%",
        padding_top="1em",
        padding_bottom="1em",
        border_right=f"1px solid {rx.color('gray', 6)}",
        background_color=rx.color("gray", 1),
        overflow="hidden",
    )


def _conversation_display(config: ChatConfig) -> rx.Component:
    """Right side conversation display."""

    return rx.box(
        rx.cond(
            HistoryState.selected_conversation_id,
            # Show selected conversation
            rx.fragment(
                read_only_chat_component(config),
                history_config_dialog(config.state),
            ),
            # Show empty state when no conversation selected
            rx.box(
                rx.icon("message-square", size=64, color=rx.color("gray", 6)),
                rx.heading("Select a Conversation", size="5", margin_top="20px"),
                rx.text(
                    "Choose a conversation from the left to view its history",
                    size="3",
                    color=rx.color("gray", 11),
                    text_align="center",
                    margin_top="12px",
                ),
                display="flex",
                flex_direction="column",
                align_items="center",
                justify_content="center",
                height="100%",
                text_align="center",
                width="100%",
            ),
        ),
        flex="1",
        height="100%",
        display="flex",
    )


def history_component(
    sources_component_builder: SourcesComponentBuilder | None = None,
    mode_badge_builder: ModeBadgeBuilder | None = None,
) -> rx.Component:
    """Complete conversation history interface with sidebar and display panel.

    This component provides a two-panel interface for browsing and viewing
    conversation history. The left panel shows a scrollable list of conversations,
    while the right panel displays the selected conversation in read-only mode.

    Features:
        - Two-panel layout with conversation list and display
        - Conversation selection and highlighting
        - Read-only conversation viewing
        - Configuration dialog for conversation settings
        - Loading states and refresh functionality

    :param sources_component_builder: Optional builder for source citation components.
    :param mode_badge_builder: Optional callable that receives a conversation mode
        ``rx.Var[str]`` and returns a badge ``rx.Component``.  Falls back to a
        plain Radix badge when *None*.
    :return: Complete history interface with sidebar and conversation display.
    """

    badge_builder = mode_badge_builder or _default_mode_badge

    config = ChatConfig(
        state=ReadOnlyChatState,
    )

    if sources_component_builder:
        config.custom_chat_messages = {
            "source": lambda message: source_message_component(
                message, ReadOnlyChatState, sources_component_builder
            ),
        }

    return rx.hstack(
        _conversations_sidebar(badge_builder),
        _conversation_display(config),
        spacing="0",
        width="100%",
        flex="1",
        min_height="0",
    )
