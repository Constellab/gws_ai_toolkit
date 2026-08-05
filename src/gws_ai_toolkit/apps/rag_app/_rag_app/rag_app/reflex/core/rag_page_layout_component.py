import reflex as rx
from gws_reflex_main import (
    main_component,
    page_sidebar_component,
    sidebar_header_component,
)

from ..history.chat_history_sidebar_component import chat_history_sidebar_list
from ..knowledge_base.chats.rag_chat_profile_list_state import CHAT_PROFILES_ROUTE
from ..knowledge_base.knowledge_bases.knowledge_base_list_state import KNOWLEDGE_BASES_ROUTE
from .conversation_mode_chip_component import conversation_mode_chip_reactive
from .rag_history_state import RagHistoryState


def rag_page_layout_component(
    content: rx.Component,
    sidebar_width: str = "300px",
) -> rx.Component:
    """Standard page layout with sidebar shared by every knowledge-base page.

    Wraps the given content with the shared sidebar containing
    app branding, New Chat button, and conversation history.

    :param content: The main page content component.
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


def _sidebar_content() -> rx.Component:
    """Sidebar content shared by every knowledge-base page.

    Contains app branding, New Chat button, and conversation history list.
    """
    return rx.vstack(
        # App branding
        sidebar_header_component(
            title="Search",
            subtitle="By Constellab",
            logo_src="/constellab-logo.svg",
            margin_bottom="1rem",
        ),
        # New Chat button, then the way into the knowledge-base pages: everything under ``/kb``
        # shares this sidebar, so these are what make those pages reachable without typing a URL.
        rx.vstack(
            rx.button(
                rx.icon("plus", size=16),
                "New Chat",
                on_click=RagHistoryState.start_new_chat,
                width="100%",
                size="2",
            ),
            rx.button(
                rx.icon("message-circle", size=16),
                "Chat profiles",
                on_click=rx.redirect(CHAT_PROFILES_ROUTE),
                variant="soft",
                width="100%",
                size="2",
            ),
            rx.button(
                rx.icon("database", size=16),
                "Knowledge bases",
                on_click=rx.redirect(KNOWLEDGE_BASES_ROUTE),
                variant="soft",
                width="100%",
                size="2",
            ),
            spacing="2",
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
