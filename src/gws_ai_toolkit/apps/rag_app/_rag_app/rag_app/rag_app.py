import reflex as rx
from gws_reflex_main import (
    get_theme,
    register_gws_reflex_app,
)

from .custom_states import CustomAppConfigState
from .reflex.ai_expert.ai_expert_component import ai_expert_component
from .reflex.ai_expert.ai_expert_config_component import ai_expert_config_component
from .reflex.ai_expert.ai_expert_state import AiExpertState
from .reflex.ai_expert.document_browser_component import document_browser_component
from .reflex.ai_expert.document_browser_state import DocumentBrowserState
from .reflex.chat_base.chat_config import ChatConfig
from .reflex.core.app_config_state import AppConfigState
from .reflex.core.page_layout_component import (
    HeaderSettingsState,
    ai_expert_header_component,
    page_layout_component,
    rag_header_component,
)
from .reflex.history.history_state import HistoryState
from .reflex.rag_chat.config.rag_config_component import rag_config_component
from .reflex.rag_chat.config.rag_config_state import RagConfigState, RagConfigStateFromParams
from .reflex.rag_chat.rag_chat_component import rag_chat_component
from .reflex.rag_chat.rag_chat_config_component import rag_chat_config_component
from .reflex.rag_chat.rag_chat_state import RagChatState
from .reflex.rag_chat.rag_empty_chat_component import rag_empty_chat_component

AppConfigState.set_config_state_class_type(CustomAppConfigState)
RagConfigState.set_rag_config_state_class_type(RagConfigStateFromParams)


app = register_gws_reflex_app(rx.App(theme=get_theme()))


_rag_chat_config = ChatConfig(
    state=RagChatState,
    empty_chat_component=rag_empty_chat_component,
    header=rag_header_component(RagChatState.subtitle),
)


@rx.page(route="/")
def index():
    """Main chat page with sidebar (new conversation)."""
    return page_layout_component(
        content=rag_chat_component(_rag_chat_config),
    )


@rx.page(route="/chat/[conversation_id]", on_load=RagChatState.load_conversation_from_url)
def chat_with_conversation():
    """Chat page for an existing conversation loaded from URL."""
    return page_layout_component(
        content=rag_chat_component(_rag_chat_config),
    )


# Resource page - for resource and sync management
@rx.page(route="/rag-config")
def rag_config():
    """Resource page for managing RAG resources and sync."""
    return rx.cond(
        HeaderSettingsState.show_settings_menu,
        page_layout_component(content=rag_config_component()),
        rx.text("RAG Config page is not available.", color="red"),
    )


# RAG Chat configuration page
@rx.page(route="/config-rag")
def config_rag_page():
    """Configuration page for RAG Chat settings."""
    return rx.cond(
        HeaderSettingsState.show_settings_menu,
        page_layout_component(content=rag_chat_config_component()),
        rx.text("Configuration page is not available.", color="red"),
    )


# AI Expert configuration page
@rx.page(route="/config-ai-expert")
def config_ai_expert_page():
    """Configuration page for AI Expert settings."""
    return rx.cond(
        HeaderSettingsState.show_settings_menu,
        page_layout_component(content=ai_expert_config_component()),
        rx.text("Configuration page is not available.", color="red"),
    )


# AI Expert page - document browser (no document selected)
@rx.page(
    route="/ai-expert",
    on_load=[DocumentBrowserState.load_documents, HistoryState.load_conversations],
)
def ai_expert_browser():
    """AI Expert page for selecting a document."""
    return page_layout_component(
        content=document_browser_component(),
    )


# AI Expert page - existing conversation loaded from URL
@rx.page(
    route="/ai-expert/chat/[conversation_id]",
    on_load=[AiExpertState.load_conversation_from_url, HistoryState.load_conversations],
)
def ai_expert_with_conversation():
    """AI Expert page for an existing conversation loaded from URL."""
    _header = ai_expert_header_component(
        AiExpertState.subtitle,
        AiExpertState.open_current_resource_file,
    )
    config = ChatConfig(state=AiExpertState, header=_header)
    return page_layout_component(
        content=ai_expert_component(config),
    )


# AI Expert page - document-specific chat (new conversation)
@rx.page(
    route="/ai-expert/[document_id]",
    on_load=[AiExpertState.load_resource_from_url, HistoryState.load_conversations],
)
def ai_expert():
    """AI Expert page for document-specific chat."""
    _header = ai_expert_header_component(
        AiExpertState.subtitle,
        AiExpertState.open_current_resource_file,
    )
    config = ChatConfig(state=AiExpertState, header=_header)
    return page_layout_component(
        content=ai_expert_component(config),
    )
