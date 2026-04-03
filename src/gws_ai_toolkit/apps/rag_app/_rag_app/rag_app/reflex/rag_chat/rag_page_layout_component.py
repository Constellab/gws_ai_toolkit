import reflex as rx
from gws_ai_toolkit.models.chat.conversation.base_chat_conversation import ChatConversationMode
from gws_reflex_main import (
    left_sidebar_open_button,
    main_component,
    page_sidebar_component,
    sidebar_header_component,
)

from ..admin_history.admin_history_state import AdminHistoryState
from ..core.conversation_mode_chip_component import (
    conversation_mode_chip_reactive,
    conversation_mode_chip_switchable,
)
from ..history.chat_history_sidebar_component import chat_history_sidebar_list
from .rag_history_state import RagHistoryState


def rag_page_layout_component(
    content: rx.Component,
    sidebar_width: str = "300px",
) -> rx.Component:
    """Standard page layout with sidebar for the RAG app.

    Wraps the given content with the shared sidebar containing
    app branding, New Chat button, and conversation history.

    :param content: The main page content component.
    :param state: The SidebarHistoryListState subclass providing start_new_chat and select_conversation.
    :param sidebar_width: Width of the sidebar.
    :return: The page layout component.
    """
    return main_component(
        page_sidebar_component(
            sidebar_content=_sidebar_content(),
            content=content,
            sidebar_width=sidebar_width,
        )
    )


def _header_divider() -> rx.Component:
    """A vertical divider line for the header."""
    return rx.box(
        width="1px",
        height="24px",
        background="var(--gray-5)",
    )


def _rag_settings_menu_button(show_settings: rx.Var[bool]) -> rx.Component:
    """Settings menu button for RAG chat header with links to Resources and Config pages.

    :param show_settings: Reactive var controlling visibility.
    """
    return rx.cond(
        show_settings,
        rx.menu.root(
            rx.menu.trigger(
                rx.button(
                    rx.icon("settings", size=16),
                    variant="ghost",
                    size="2",
                    cursor="pointer",
                    color="var(--gray-11)",
                ),
            ),
            rx.menu.content(
                rx.menu.item(
                    rx.icon("database", size=16),
                    "Resources",
                    on_click=rx.redirect("/rag-config"),
                ),
                rx.menu.item(
                    rx.icon("settings", size=16),
                    "Config",
                    on_click=rx.redirect("/config-rag"),
                ),
                rx.cond(
                    AdminHistoryState.show_admin_history,
                    rx.menu.item(
                        rx.icon("users", size=16),
                        "Admin History",
                        on_click=rx.redirect("/admin-history"),
                    ),
                ),
            ),
        ),
    )


def rag_header_component(
    subtitle: rx.Var[str | None], show_settings: rx.Var[bool] | None = None
) -> rx.Component:
    """Header for RAG chat pages showing the chat mode and file count.

    :param subtitle: Reactive var with the file count text (e.g. "5 files in the database").
    :param show_settings: Reactive var controlling settings button visibility.
    :return: The header component.
    """
    return rx.hstack(
        left_sidebar_open_button(),
        conversation_mode_chip_switchable(ChatConversationMode.RAG.value, size="big"),
        _header_divider(),
        rx.hstack(
            rx.icon("database", size=16, color="var(--gray-9)"),
            rx.cond(
                subtitle,
                rx.text(subtitle, size="2", color="var(--gray-11)"),
                rx.text("Loading...", size="2", color="var(--gray-8)"),
            ),
            align="center",
            spacing="2",
        ),
        rx.spacer(),
        _rag_settings_menu_button(show_settings) if show_settings is not None else rx.fragment(),
        align="center",
        spacing="3",
        width="100%",
    )


def _sidebar_content() -> rx.Component:
    """Sidebar content for the RAG app pages.

    Contains app branding, New Chat button, and conversation history list.

    :param state: The SidebarHistoryListState subclass providing start_new_chat and select_conversation.
    """
    return rx.vstack(
        # App branding
        sidebar_header_component(
            title="Search",
            subtitle="By Constellab",
            logo_src="/constellab-logo.svg",
            margin_bottom="1rem",
        ),
        # New Chat button
        rx.box(
            rx.button(
                rx.icon("plus", size=16),
                "New Chat",
                on_click=RagHistoryState.start_new_chat,
                width="100%",
                size="2",
            ),
            padding="0 1rem 1rem 1rem",
            width="100%",
        ),
        # Conversation history list (takes remaining space)
        rx.box(
            chat_history_sidebar_list(
                state=RagHistoryState, mode_badge_builder=conversation_mode_chip_reactive
            ),
            flex="1",
            min_height="0",
            overflow_y="auto",
            width="100%",
            padding_inline="1rem",
        ),
        width="100%",
        height="100%",
        spacing="0",
    )
