import reflex as rx
from gws_ai_toolkit.models.chat.chat_conversation_dto import ChatConversationDTO

from ..history.history_state import HistoryState
from .chat_history_sidebar_state import ChatHistorySidebarState


def _sidebar_conversation_item(conversation: ChatConversationDTO) -> rx.Component:
    """Individual conversation item in the chat sidebar."""
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
            rx.text(
                rx.moment(conversation.last_modified_at, from_now=True),
                size="1",
                color=rx.color("gray", 9),
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
        on_click=ChatHistorySidebarState.select_conversation(conversation.id),
        width="100%",
    )


def chat_history_sidebar_list() -> rx.Component:
    """Conversation history list component for use inside a sidebar.

    Displays the list of past conversations with loading and empty states.
    Does not include app branding or "New Chat" button — those should be
    added by the parent sidebar layout.

    Returns:
        rx.Component: The conversation list component.
    """
    return rx.cond(
        HistoryState.is_loading,
        rx.center(rx.spinner(size="3"), padding="20px"),
        rx.cond(
            HistoryState.has_conversations,
            rx.vstack(
                rx.foreach(
                    HistoryState.conversations,
                    _sidebar_conversation_item,
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
    )
