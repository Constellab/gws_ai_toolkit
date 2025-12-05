import reflex as rx
import reflex_enterprise as rxe
from gws_reflex_main import register_gws_reflex_app

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
from .reflex.rag_chat.config.rag_config_component import rag_config_component
from .reflex.rag_chat.config.rag_config_state import RagConfigState, RagConfigStateFromParams
from .reflex.rag_chat.rag_chat_component import rag_chat_component

AppConfigState.set_config_state_class_type(CustomAppConfigState)
RagConfigState.set_rag_config_state_class_type(RagConfigStateFromParams)


app = register_gws_reflex_app(rxe.App())

nav_bar_items: list[NavBarItem] = [
    NavBarItem(text="Chat", icon="message-circle", url="/"),
    NavBarItem(text="AI Expert", icon="brain", url="/ai-expert"),
    NavBarItem(text="Resources", icon="database", url="/rag-config"),
    NavBarItem(text="Config", icon="settings", url="/config"),
    NavBarItem(text="History", icon="clock", url="/history"),
]


@rx.page(route="/")
def index():
    """Main chat page."""
    return page_component(nav_bar_items, rag_chat_component())


# Resource page - for resource and sync management
@rx.page(route="/rag-config")
def rag_config():
    """Resource page for managing RAG resources and sync."""
    return page_component(nav_bar_items, rag_config_component())


# Configuration page - for AI Expert and AI Table configurations
@rx.page(route="/config")
def config_page():
    """Configuration page for AI Expert and AI Table settings."""
    return page_component(nav_bar_items, combined_config_page())


# History page - for conversation history
@rx.page(route="/history", on_load=HistoryState.load_conversations)
def history():
    """History page for viewing conversation history."""
    return page_component(nav_bar_items, history_component())


# AI Expert page - document browser (no document selected)
@rx.page(route="/ai-expert", on_load=DocumentBrowserState.load_documents)
def ai_expert_browser():
    """AI Expert page for selecting a document."""
    return page_component(nav_bar_items, document_browser_component())


# AI Expert page - document-specific chat
@rx.page(route="/ai-expert/[document_id]", on_load=AiExpertState.load_resource_from_url)
def ai_expert():
    """AI Expert page for document-specific chat."""
    config = ChatConfig(
        state=AiExpertState,
        header_buttons=ai_expert_header_default_buttons_component,
    )
    return page_component(nav_bar_items, ai_expert_component(config))
