import reflex as rx
from gws_ai_toolkit.models.chat.chat_conversation_dto import AdminChatConversationDTO
from gws_ai_toolkit.models.chat.conversation.base_chat_conversation import ChatConversationMode
from gws_reflex_main import main_component, user_select

from ..chat_base.chat_config import ChatConfig
from ..chat_base.messages_list_component import chat_messages_list_component
from ..core.conversation_mode_chip_component import conversation_mode_chip_reactive
from .admin_history_state import AdminHistoryState


def admin_history_list_component() -> rx.Component:
    """Admin conversation history list page component.

    Shows a filterable table of all conversations from all users.
    Clicking a row navigates to the detail page.

    :return: The admin history list page component.
    """
    return main_component(
        rx.vstack(
            _admin_history_header(),
            _filter_bar(),
            rx.cond(
                AdminHistoryState.is_loading,
                rx.center(rx.spinner(size="3"), padding="40px"),
                rx.cond(
                    AdminHistoryState.conversations.length() > 0,
                    _conversation_table(),
                    rx.center(
                        rx.vstack(
                            rx.icon("message-circle", size=32, color="var(--gray-6)"),
                            rx.text(
                                "No conversations yet",
                                size="2",
                                color="var(--gray-9)",
                            ),
                            align="center",
                            spacing="2",
                        ),
                        padding="40px 20px",
                    ),
                ),
            ),
            on_mount=AdminHistoryState.load_all_conversations,
            width="100%",
            height="100%",
            spacing="4",
            padding="24px",
        ),
    )


def admin_history_detail_component() -> rx.Component:
    """Admin conversation detail page component.

    Shows a back button and readonly messages for a single conversation.

    :return: The admin history detail page component.
    """
    config = ChatConfig(state=AdminHistoryState)  # type: ignore

    return main_component(
        rx.vstack(
            # Header with back button and conversation info
            rx.hstack(
                rx.button(
                    rx.icon("arrow-left", size=16),
                    "Back to History",
                    variant="ghost",
                    size="2",
                    cursor="pointer",
                    on_click=rx.redirect("/admin-history"),
                ),
                rx.separator(orientation="vertical", size="2"),
                rx.vstack(
                    rx.text(
                        AdminHistoryState.selected_conversation_label,
                        size="3",
                        font_weight="600",
                    ),
                    rx.text(
                        AdminHistoryState.selected_conversation_user,
                        size="2",
                        color="var(--gray-9)",
                    ),
                    spacing="0",
                ),
                align="center",
                spacing="3",
                width="100%",
                padding_bottom="12px",
                border_bottom="1px solid var(--gray-5)",
            ),
            # Messages
            rx.cond(
                AdminHistoryState.is_loading_messages,
                rx.center(rx.spinner(size="3"), padding="40px"),
                rx.box(
                    chat_messages_list_component(config),
                    overflow_y="auto",
                    flex="1",
                    width="100%",
                ),
            ),
            width="100%",
            max_width="900px",
            height="100vh",
            margin_x="auto",
            spacing="4",
            padding="24px",
        ),
    )


def _admin_history_header() -> rx.Component:
    """Header for the admin history list page."""
    return rx.hstack(
        rx.button(
            rx.icon("home", size=16),
            variant="ghost",
            size="2",
            cursor="pointer",
            on_click=rx.redirect("/"),
        ),
        rx.separator(orientation="vertical", size="2"),
        rx.icon("users", size=20, color="var(--gray-11)"),
        rx.heading("Admin History", size="5"),
        align="center",
        spacing="3",
        width="100%",
    )


def _filter_bar() -> rx.Component:
    """Filter bar with label search, mode select, and user select."""
    return rx.hstack(
        rx.input(
            rx.input.slot(rx.icon("search", size=16)),
            placeholder="Search by label...",
            value=AdminHistoryState.filter_label,
            on_change=AdminHistoryState.set_filter_label,
            min_width="300px",
        ),
        rx.select.root(
            rx.select.trigger(placeholder="All modes", width="180px"),
            rx.select.content(
                rx.select.item("Chat", value=ChatConversationMode.RAG.value),
                rx.select.item("AI Expert", value=ChatConversationMode.AI_EXPERT.value),
                rx.select.item("AI Table", value=ChatConversationMode.AI_TABLE.value),
            ),
            value=AdminHistoryState.filter_mode,
            on_change=AdminHistoryState.set_filter_mode,
        ),
        user_select(
            users=AdminHistoryState.users,
            placeholder="All users",
            width="220px",
            value=AdminHistoryState.filter_user_id,
            on_change=AdminHistoryState.set_filter_user,
        ),
        rx.button(
            "Clear",
            on_click=AdminHistoryState.clear_filters,
            variant="surface",
            size="2",
            color_scheme="gray",
            radius="large",
        ),
        width="100%",
        spacing="3",
        wrap="wrap",
    )


def _conversation_row(conversation: AdminChatConversationDTO) -> rx.Component:
    """A single row in the conversation table.

    :param conversation: The conversation DTO to render.
    :return: A clickable table row component.
    """
    user_name = conversation.user_first_name + " " + conversation.user_last_name
    return rx.table.row(
        rx.table.cell(
            rx.text(
                rx.cond(
                    conversation.label.length() > 50,
                    conversation.label[:50] + "...",
                    conversation.label,
                ),
                size="2",
                font_weight="500",
            ),
        ),
        rx.table.cell(conversation_mode_chip_reactive(conversation.mode)),
        rx.table.cell(
            rx.text(user_name, size="2"),
        ),
        rx.table.cell(
            rx.text(conversation.user_email, size="2", color="var(--gray-9)"),
        ),
        rx.table.cell(
            rx.text(
                rx.moment(conversation.last_modified_at, from_now=True),
                size="1",
                color="var(--gray-9)",
            ),
        ),
        cursor="pointer",
        _hover={"background_color": "var(--gray-3)"},
        on_click=rx.redirect(
            "/admin-history/" + conversation.id,
        ),
    )


def _conversation_table() -> rx.Component:
    """Table listing all conversations."""
    return rx.table.root(
        rx.table.header(
            rx.table.row(
                rx.table.column_header_cell("Label"),
                rx.table.column_header_cell("Mode"),
                rx.table.column_header_cell("User"),
                rx.table.column_header_cell("Email"),
                rx.table.column_header_cell("Last Modified"),
            ),
        ),
        rx.table.body(
            rx.foreach(
                AdminHistoryState.conversations,
                _conversation_row,
            ),
        ),
        width="100%",
    )
