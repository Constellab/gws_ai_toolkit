from typing import List

import reflex as rx

from ..chat_base.chat_config import ChatConfig
from ..chat_base.sources_list_component import sources_list_component
from ..read_only_chat.read_only_chat_interface import read_only_chat_component
from ..read_only_chat.read_only_chat_state import ReadOnlyChatState
from .conversation_history_class import ConversationHistory
from .history_config_dialog import history_config_dialog
from .history_state import HistoryState


def _conversation_item(conversation: ConversationHistory) -> rx.Component:
    """Individual conversation item component."""

    # Format mode display
    mode_display = conversation.mode.replace('_', ' ').title()

    return rx.box(
        rx.vstack(
            rx.hstack(
                rx.heading(
                    rx.cond(
                        conversation.label.length() > 60,
                        conversation.label[:60] + "...",
                        conversation.label
                    ),
                    size="3",
                    margin_bottom="4px",
                    font_weight="600",
                ),
                rx.spacer(),
                width="100%"
            ),
            rx.hstack(
                rx.badge(mode_display, size="1", variant="soft"),
                rx.spacer(),
                rx.text(
                    rx.moment(
                        conversation.timestamp,
                        format="MMM D, YYYY h:mm"
                    ),
                    size="2",
                    color=rx.color("gray", 11)
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
            HistoryState.selected_conversation_id == conversation.conversation_id,
            f"2px solid {rx.color('accent', 8)}",
            f"1px solid {rx.color('gray', 6)}"
        ),
        background_color=rx.cond(
            HistoryState.selected_conversation_id == conversation.conversation_id,
            rx.color("accent", 3),
            "white"
        ),
        _hover={
            "background_color": rx.cond(
                HistoryState.selected_conversation_id == conversation.conversation_id,
                rx.color("accent", 4),
                rx.color("gray", 2)
            ),
        },
        on_click=lambda: HistoryState.select_conversation(conversation.conversation_id),
        margin_bottom="8px",
        width="100%",
    )


def _conversations_sidebar() -> rx.Component:
    """Left sidebar with conversation list."""
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
                    cursor="pointer",
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
                    text_align="center"
                ),
                # Content when not loading
                rx.cond(
                    HistoryState.has_conversations,
                    # Show conversations list
                    rx.vstack(
                        rx.foreach(
                            HistoryState.conversations,
                            _conversation_item
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
                            margin_top="8px"
                        ),
                        display="flex",
                        flex_direction="column",
                        align_items="center",
                        justify_content="center",
                        padding="40px 20px",
                        text_align="center"
                    )
                )
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


def _header_buttons(state: ReadOnlyChatState) -> List[rx.Component]:

    return [
        rx.button(
            rx.icon("settings", size=16),
            "Configuration",
            variant="outline",
            size="2",
            cursor="pointer",
            on_click=state.open_config_dialog
        )
    ]


def _conversation_display() -> rx.Component:
    """Right side conversation display."""
    config = ChatConfig(
        state=ReadOnlyChatState,
        sources_component=sources_list_component,
        header_buttons=_header_buttons
    )

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
                    margin_top="12px"
                ),
                display="flex",
                flex_direction="column",
                align_items="center",
                justify_content="center",
                height="100%",
                text_align="center",
                width="100%",
            )
        ),
        flex="1",
        height="100%",
        display="flex",
    )


def history_component():
    return rx.hstack(
        _conversations_sidebar(),
        _conversation_display(),
        spacing="0",
        width="100%",
        flex="1",
        min_height="0",
    )
