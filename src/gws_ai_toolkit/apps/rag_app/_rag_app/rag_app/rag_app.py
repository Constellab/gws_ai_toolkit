import reflex as rx
from gws_reflex_main import (
    ReflexDownloadService,
    register_gws_reflex_app,
)

from .custom_states import CustomAppConfigState
from .reflex.admin_history.admin_history_component import (
    admin_history_detail_component,
    admin_history_list_component,
)
from .reflex.admin_history.admin_history_state import AdminHistoryState
from .reflex.core.app_config_state import AppConfigState
from .reflex.core.rag_page_layout_component import rag_page_layout_component
from .reflex.knowledge_base.chat.knowledge_base_chat_component import (
    knowledge_base_chat_component,
)
from .reflex.knowledge_base.chat.knowledge_base_chat_state import KnowledgeBaseChatState
from .reflex.knowledge_base.chats.rag_chat_profile_detail_component import (
    rag_chat_profile_detail_component,
)
from .reflex.knowledge_base.chats.rag_chat_profile_detail_state import (
    RagChatProfileDetailState,
)
from .reflex.knowledge_base.chats.rag_chat_profile_list_component import (
    rag_chat_profile_list_component,
)
from .reflex.knowledge_base.chats.rag_chat_profile_list_state import RagChatProfileListState
from .reflex.knowledge_base.knowledge_bases.knowledge_base_detail_component import (
    knowledge_base_detail_component,
)
from .reflex.knowledge_base.knowledge_bases.knowledge_base_detail_state import (
    KnowledgeBaseDetailState,
)
from .reflex.knowledge_base.knowledge_bases.knowledge_base_list_component import (
    knowledge_base_list_component,
)
from .reflex.knowledge_base.knowledge_bases.knowledge_base_list_state import KnowledgeBaseListState

AppConfigState.set_config_state_class_type(CustomAppConfigState)


# Theme is configured via RadixThemesPlugin in rxconfig.py (App(theme=...) is
# deprecated), so the app is created without an explicit theme here.
app = register_gws_reflex_app(rx.App())

# Serves knowledge-base document snapshots over HTTP: a 15 MB file pushed through the websocket event
# channel would freeze the UI while it travels. Required by ``build_open_document_event``.
app.api_transformer = ReflexDownloadService.build_api()


# Admin history - list page
@rx.page(route="/admin-history")
def admin_history():
    """Admin page showing all conversations from all users."""
    return rx.cond(
        AdminHistoryState.show_admin_history,
        admin_history_list_component(),
        rx.text("Admin History page is not available.", color="red"),
    )


# Admin history - detail page
@rx.page(
    route="/admin-history/[conversation_id]",
    on_load=AdminHistoryState.load_conversation_from_url,
)
def admin_history_detail():
    """Admin page showing readonly messages of a single conversation."""
    return rx.cond(
        AdminHistoryState.show_admin_history,
        admin_history_detail_component(),
        rx.text("Admin History page is not available.", color="red"),
    )


# Knowledge-base chat - new conversation
@rx.page(route="/", on_load=KnowledgeBaseChatState.load_new_chat_page)
def knowledge_base_chat():
    """Chat against a chat profile, answering from the knowledge bases it is bound to."""
    return rag_page_layout_component(
        content=knowledge_base_chat_component(),
    )


# Knowledge-base chat - existing conversation loaded from the URL
@rx.page(
    route="/chat/[conversation_id]",
    on_load=KnowledgeBaseChatState.load_conversation_from_url,
)
def knowledge_base_chat_with_conversation():
    """A persisted knowledge-base conversation, restored from its id."""
    return rag_page_layout_component(
        content=knowledge_base_chat_component(),
    )


# Chat profiles - list and edit page
@rx.page(route="/kb/chats", on_load=RagChatProfileListState.load_page)
def chat_profiles():
    """Chat profiles: create one, configure it, and bind the knowledge bases it searches."""
    return rag_page_layout_component(
        content=rag_chat_profile_list_component(),
    )


# Chat profiles - detail page
@rx.page(
    route="/kb/chats/[chat_profile_id]",
    on_load=RagChatProfileDetailState.load_profile,
)
def chat_profile_detail():
    """One chat profile: its prompt, its retrieval settings, what it searches and its publication."""
    return rag_page_layout_component(
        content=rag_chat_profile_detail_component(),
    )


# Knowledge bases - list page
@rx.page(route="/kb/bases", on_load=KnowledgeBaseListState.load_knowledge_bases)
def knowledge_bases():
    """Knowledge-base manager: list, create and delete knowledge bases."""
    return rag_page_layout_component(
        content=knowledge_base_list_component(),
    )


# Knowledge bases - detail page
@rx.page(
    route="/kb/bases/[knowledge_base_id]",
    on_load=KnowledgeBaseDetailState.load_knowledge_base,
)
def knowledge_base_detail():
    """One knowledge base: its documents, their indexing status and the actions on them."""
    return rag_page_layout_component(
        content=knowledge_base_detail_component(),
    )
