from typing import List

import reflex as rx
from gws_reflex_base import render_main_container

from gws_ai_toolkit.rag.rag_app._rag_app.rag_app.components.conversation_history.conversation_history_class import \
    ConversationHistory
from gws_ai_toolkit.rag.rag_app._rag_app.rag_app.components.generic_chat.chat_config import \
    ChatConfig
from gws_ai_toolkit.rag.rag_app._rag_app.rag_app.components.generic_chat.generic_sources_list import \
    generic_sources_list
from gws_ai_toolkit.rag.rag_app._rag_app.rag_app.components.generic_chat.read_only_chat_interface import \
    read_only_chat_interface
from gws_ai_toolkit.rag.rag_app._rag_app.rag_app.components.generic_chat.read_only_chat_state import \
    ReadOnlyChatState
from gws_ai_toolkit.rag.rag_app._rag_app.rag_app.components.shared.navigation import \
    navigation

from .history_page_state import HistoryPageState


def conversation_item(conversation: ConversationHistory) -> rx.Component:
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
            HistoryPageState.selected_conversation_id == conversation.conversation_id,
            f"2px solid {rx.color('accent', 8)}",
            f"1px solid {rx.color('gray', 6)}"
        ),
        background_color=rx.cond(
            HistoryPageState.selected_conversation_id == conversation.conversation_id,
            rx.color("accent", 3),
            "white"
        ),
        _hover={
            "background_color": rx.cond(
                HistoryPageState.selected_conversation_id == conversation.conversation_id,
                rx.color("accent", 4),
                rx.color("gray", 2)
            ),
        },
        on_click=lambda: HistoryPageState.select_conversation(conversation.conversation_id),
        margin_bottom="8px",
        width="100%",
    )


def conversations_sidebar() -> rx.Component:
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
                    on_click=HistoryPageState.load_conversations,
                    cursor="pointer",
                ),
                width="100%",
                align_items="center",
                margin_bottom="16px"
            ),

            # Loading state
            rx.cond(
                HistoryPageState.is_loading,
                rx.box(
                    rx.spinner(size="3"),
                    rx.text("Loading conversations...", size="2", color=rx.color("gray", 11)),
                    padding="20px",
                    text_align="center"
                ),
                # Content when not loading
                rx.cond(
                    HistoryPageState.has_conversations,
                    # Show conversations list
                    rx.auto_scroll(
                        rx.vstack(
                            rx.foreach(
                                HistoryPageState.conversations,
                                conversation_item
                            ),
                            spacing="0",
                            width="100%",
                        ),
                        width="100%",
                        max_height="calc(100vh - 200px)",
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
        padding="20px",
        border_right=f"1px solid {rx.color('gray', 6)}",
        background_color=rx.color("gray", 1),
        overflow="hidden",
    )


def _header_buttons(_) -> List[rx.Component]:
    return []


def conversation_display() -> rx.Component:
    """Right side conversation display."""
    config = ChatConfig(
        state=ReadOnlyChatState,
        sources_component=generic_sources_list,
        header_buttons=_header_buttons
    )

    return rx.box(
        rx.cond(
            HistoryPageState.selected_conversation_id,
            # Show selected conversation
            read_only_chat_interface(config),
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
                text_align="center"
            )
        ),
        flex="1",
        height="100%",
        overflow="hidden",
    )


def history_page() -> rx.Component:
    """History page component."""
    return render_main_container(
        rx.vstack(
            navigation(),
            rx.hstack(
                conversations_sidebar(),
                conversation_display(),
                spacing="0",
                width="100%",
                height="calc(100vh - 60px)",  # Account for navigation height
                overflow="hidden"
            ),
            spacing="0",
            width="100%",
            height="100vh",
        )
    )
