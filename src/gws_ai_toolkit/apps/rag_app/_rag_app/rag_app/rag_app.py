import reflex as rx
from gws_reflex_main import (
    get_theme,
    page_sidebar_component,
    register_gws_reflex_app,
    sidebar_header_component,
)
from gws_reflex_main.reflex_main_state import ReflexMainState

from .config_page import combined_config_page
from .custom_states import CustomAppConfigState
from .reflex.ai_expert.ai_expert_component import (
    ai_expert_component,
    ai_expert_header_default_buttons_component,
)
from .reflex.ai_expert.ai_expert_state import AiExpertState
from .reflex.ai_expert.document_browser_component import document_browser_component
from .reflex.ai_expert.document_browser_state import DocumentBrowserState
from .reflex.chat_base.chat_config import ChatConfig
from .reflex.core.app_config_state import AppConfigState
from .reflex.core.nav_bar_component import NavBarItem
from .reflex.core.page_component import page_component
from .reflex.history.history_component import history_component
from .reflex.history.history_state import HistoryState
from .reflex.rag_chat.chat_history_sidebar_component import chat_history_sidebar_list
from .reflex.rag_chat.chat_history_sidebar_state import ChatHistorySidebarState
from .reflex.rag_chat.config.rag_config_component import rag_config_component
from .reflex.rag_chat.config.rag_config_state import RagConfigState, RagConfigStateFromParams
from .reflex.rag_chat.rag_chat_component import rag_chat_component
from .reflex.rag_chat.rag_chat_state import RagChatState
from .reflex.rag_chat.rag_empty_chat_component import rag_empty_chat_component

AppConfigState.set_config_state_class_type(CustomAppConfigState)
RagConfigState.set_rag_config_state_class_type(RagConfigStateFromParams)


app = register_gws_reflex_app(rx.App(theme=get_theme()))


class NavBarState(rx.State):
    @rx.var
    async def show_config_page(self) -> bool:
        """Determine if the Config page should be shown in the nav bar."""
        main_state = await self.get_state(ReflexMainState)
        show_config_page = await main_state.get_param("show_config_page", False)
        return show_config_page

    @rx.var
    async def nav_bar_items(self) -> list[NavBarItem]:
        nav_bar_items: list[NavBarItem] = [
            NavBarItem(text="Chat", icon="message-circle", url="/"),
            NavBarItem(text="AI Expert", icon="brain", url="/ai-expert"),
        ]

        show_config_page = await self.show_config_page
        if show_config_page:
            nav_bar_items.append(
                NavBarItem(text="Resources", icon="database", url="/rag-config"),
            )
            nav_bar_items.append(
                NavBarItem(text="Config", icon="settings", url="/config"),
            )

        nav_bar_items.append(NavBarItem(text="History", icon="clock", url="/history"))

        return nav_bar_items


def _chat_sidebar_content() -> rx.Component:
    """Sidebar content for the main chat page.

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
            chat_history_sidebar_list(),
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


_rag_chat_config = ChatConfig(
    state=RagChatState,
    empty_chat_component=rag_empty_chat_component,
)


@rx.page(route="/")
def index():
    """Main chat page with sidebar (new conversation)."""
    return page_sidebar_component(
        sidebar_content=_chat_sidebar_content(),
        content=rag_chat_component(_rag_chat_config),
        sidebar_width="300px",
    )


@rx.page(route="/chat/[conversation_id]", on_load=RagChatState.load_conversation_from_url)
def chat_with_conversation():
    """Chat page for an existing conversation loaded from URL."""
    return page_sidebar_component(
        sidebar_content=_chat_sidebar_content(),
        content=rag_chat_component(_rag_chat_config),
        sidebar_width="300px",
    )


# Resource page - for resource and sync management
@rx.page(route="/rag-config")
def rag_config():
    """Resource page for managing RAG resources and sync."""
    return rx.cond(
        NavBarState.show_config_page,
        page_component(NavBarState.nav_bar_items, rag_config_component()),
        rx.text("RAG Config page is not available.", color="red"),
    )


# Configuration page - for AI Expert and AI Table configurations
@rx.page(route="/config")
def config_page():
    """Configuration page for AI Expert and AI Table settings."""
    return rx.cond(
        NavBarState.show_config_page,
        page_component(NavBarState.nav_bar_items, combined_config_page()),
        rx.text("Configuration page is not available.", color="red"),
    )


# History page - for conversation history
@rx.page(route="/history", on_load=HistoryState.load_conversations)
def history():
    """History page for viewing conversation history."""
    return page_component(NavBarState.nav_bar_items, history_component())


# AI Expert page - document browser (no document selected)
@rx.page(route="/ai-expert", on_load=DocumentBrowserState.load_documents)
def ai_expert_browser():
    """AI Expert page for selecting a document."""
    return page_component(NavBarState.nav_bar_items, document_browser_component())


# AI Expert page - document-specific chat
@rx.page(route="/ai-expert/[document_id]", on_load=AiExpertState.load_resource_from_url)
def ai_expert():
    """AI Expert page for document-specific chat."""
    config = ChatConfig(
        state=AiExpertState,
        header_buttons=ai_expert_header_default_buttons_component,
    )
    return page_component(NavBarState.nav_bar_items, ai_expert_component(config))
