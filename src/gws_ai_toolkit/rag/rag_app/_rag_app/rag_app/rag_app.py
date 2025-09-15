from typing import List

import reflex as rx
import reflex_enterprise as rxe
from gws_reflex_base import add_unauthorized_page, get_theme

from .config_page import combined_config_page
from .custom_ai_expert_component import custom_left_sidebar
from .custom_ai_expert_state import CustomAssociatedResourceAiExpertState
# Import custom states to let reflex instantiate them
from .custom_states import (CustomAppConfigState,
                            CustomConversationHistoryState,
                            CustomRagConfigState)
from .reflex.ai_expert.ai_expert_component import (
    ai_expert_component, ai_expert_header_default_buttons_component)
from .reflex.ai_expert.ai_expert_state import AiExpertState
from .reflex.chat_base.chat_config import ChatConfig
from .reflex.core.nav_bar_component import NavBarItem
from .reflex.core.page_component import page_component
from .reflex.history.history_component import history_component
from .reflex.history.history_state import HistoryState
from .reflex.rag_chat.config.rag_config_component import rag_config_component
from .reflex.rag_chat.rag_chat_component import rag_chat_component

app = rxe.App(
    theme=get_theme(),
    stylesheets=["/style.css"],
)

nav_bar_items: List[NavBarItem] = [
    NavBarItem(text="Chat", icon="message-circle", url="/"),
    NavBarItem(text="Resources", icon="database", url="/rag-config"),
    NavBarItem(text="Config", icon="settings", url="/config"),
    NavBarItem(text="History", icon="clock", url="/history"),
]


@rx.page(route="/")
def index():
    """Main chat page."""
    return page_component(
        nav_bar_items,
        rag_chat_component()
    )


# Resource page - for resource and sync management
@rx.page(route="/rag-config")
def rag_config():
    """Resource page for managing RAG resources and sync."""
    return page_component(
        nav_bar_items,
        rag_config_component()
    )


# Configuration page - for AI Expert and AI Table configurations
@rx.page(route="/config")
def config_page():
    """Configuration page for AI Expert and AI Table settings."""
    return page_component(
        nav_bar_items,
        combined_config_page()
    )


# History page - for conversation history
@rx.page(route="/history", on_load=HistoryState.load_conversations)
def history():
    """History page for viewing conversation history."""
    return page_component(
        nav_bar_items,
        history_component(CustomConversationHistoryState)
    )


# AI Expert page - document-specific chat
@rx.page(route="/ai-expert/[document_id]")
def ai_expert():
    """AI Expert page for document-specific chat."""
    config = ChatConfig(
        state=AiExpertState,
        header_buttons=ai_expert_header_default_buttons_component,
        left_section=lambda x: custom_left_sidebar(x, CustomAssociatedResourceAiExpertState)
    )
    return page_component(
        nav_bar_items,
        ai_expert_component(config)
    )


# AI Table page - Excel/CSV-specific data analysis
# @rx.page(route="/ai-table/[resource_id]", on_load=AiTableState.load_resource_from_id)
# def ai_table():
#     """AI Table page for Excel/CSV data analysis."""
#     return page_component(
#         nav_bar_items,
#         ai_table_component(),
#         disable_padding=True
#     )


# Add the unauthorized page to the app.
# This page will be displayed if the user is not authenticated
add_unauthorized_page(app)
