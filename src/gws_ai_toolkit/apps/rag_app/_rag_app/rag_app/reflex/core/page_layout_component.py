import reflex as rx
from gws_reflex_main import (
    left_sidebar_open_button,
    page_sidebar_component,
    sidebar_header_component,
)

from ..rag_chat.chat_history_sidebar_component import chat_history_sidebar_list
from ..rag_chat.chat_history_sidebar_state import ChatHistorySidebarState
from .conversation_mode_chip_component import conversation_mode_chip_reactive


def page_layout_component(
    content: rx.Component,
    sidebar_width: str = "300px",
) -> rx.Component:
    """Standard page layout with sidebar for the RAG app.

    Wraps the given content with the shared sidebar containing
    app branding, New Chat button, and conversation history.

    :param content: The main page content component.
    :param sidebar_width: Width of the sidebar.
    :return: The page layout component.
    """
    return page_sidebar_component(
        sidebar_content=_sidebar_content(),
        content=content,
        sidebar_width=sidebar_width,
    )


def _header_divider() -> rx.Component:
    """A vertical divider line for the header."""
    return rx.box(
        width="1px",
        height="24px",
        background="var(--gray-5)",
    )


def rag_header_component(subtitle: rx.Var[str | None]) -> rx.Component:
    """Header for RAG chat pages showing the chat mode and file count.

    :param subtitle: Reactive var with the file count text (e.g. "5 files in the database").
    :return: The header component.
    """
    return rx.hstack(
        left_sidebar_open_button(),
        conversation_mode_chip_reactive("rag", size="big"),
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
        align="center",
        spacing="3",
        width="100%",
    )


def ai_expert_header_component(
    subtitle: rx.Var[str | None],
    on_view_document: rx.EventChain,
) -> rx.Component:
    """Header for AI Expert pages showing the mode, document name, and view button.

    :param subtitle: Reactive var with the document/resource name.
    :param on_view_document: Event handler for the "View document" button.
    :return: The header component.
    """
    return rx.hstack(
        left_sidebar_open_button(),
        conversation_mode_chip_reactive("ai_expert", size="big"),
        _header_divider(),
        rx.hstack(
            rx.icon("file-text", size=16, color="var(--gray-9)"),
            rx.cond(
                subtitle,
                rx.text(subtitle, size="2", weight="medium", color="var(--gray-12)"),
                rx.text("Loading...", size="2", color="var(--gray-8)"),
            ),
            align="center",
            spacing="2",
        ),
        rx.spacer(),
        rx.button(
            rx.icon("eye", size=14),
            "View document",
            on_click=on_view_document,
            variant="solid",
            size="2",
        ),
        align="center",
        spacing="3",
        width="100%",
    )


def _sidebar_content() -> rx.Component:
    """Sidebar content for the RAG app pages.

    Contains app branding, New Chat button, and conversation history list.
    """
    return rx.vstack(
        # App branding
        sidebar_header_component(
            title="Search",
            subtitle="By Constellab",
            logo_src="/constellab-logo.svg",
        ),
        # New Chat button
        rx.box(
            rx.button(
                rx.icon("plus", size=16),
                "New Chat",
                on_click=ChatHistorySidebarState.start_new_chat,
                width="100%",
                size="2",
            ),
            padding="0 1rem 1rem 1rem",
            width="100%",
        ),
        # Conversation history list (takes remaining space)
        rx.box(
            chat_history_sidebar_list(mode_badge_builder=conversation_mode_chip_reactive),
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
