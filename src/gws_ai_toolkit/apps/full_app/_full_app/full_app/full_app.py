import reflex as rx
from gws_ai_toolkit._app.ai_chat import AppConfigState, ConversationChatStateBase
from gws_ai_toolkit._app.ai_knowledge_base import (
    AdminHistoryState,
    KnowledgeBaseChatState,
    KnowledgeBaseDetailState,
    KnowledgeBaseListState,
    RagChatProfileListState,
    admin_history_detail_component,
    admin_history_list_component,
    knowledge_base_chat_component,
    knowledge_base_chat_config_factory,
    knowledge_base_detail_component,
    knowledge_base_list_component,
    knowledge_base_source_menu_items,
    rag_chat_profile_list_component,
    rag_page_layout_component,
)
from gws_ai_toolkit._app.ai_table import (
    AiTableDataState,
    ai_table_agent_chat_config_component,
    ai_table_component,
)
from gws_ai_toolkit.models.chat.message.chat_message_source import RagChatSourceFront
from gws_reflex_main import ReflexDownloadService, main_component, register_gws_reflex_app

from .associated_resources_component import associated_resources_dialog
from .associated_resources_state import AssociatedResourcesState
from .custom_states import CustomAppConfigState

AppConfigState.set_config_state_class_type(CustomAppConfigState)

# Theme is configured via RadixThemesPlugin in rxconfig.py (App(theme=...) is
# deprecated), so the app is created without an explicit theme here.
app = register_gws_reflex_app(rx.App())

# Serves knowledge-base document snapshots over HTTP: a 15 MB file pushed through the websocket event
# channel would freeze the UI while it travels. Required by ``build_open_document_event``.
app.api_transformer = ReflexDownloadService.build_api()


def custom_source_menu_items(
    source: RagChatSourceFront, state: ConversationChatStateBase
) -> list[rx.Component]:
    items = knowledge_base_source_menu_items(source, state)
    items.append(
        rx.menu.item(
            rx.icon("link", size=16),
            "Associated resources",
            on_click=lambda: AssociatedResourcesState.open_associated_resources_dialog(
                source.document_id
            ),
        )
    )
    return items


_kb_chat_config = knowledge_base_chat_config_factory(custom_source_menu_items)


def _chat_page_content() -> rx.Component:
    """The knowledge-base chat, wrapped with the associated-resources dialog it can open."""
    return rag_page_layout_component(
        content=rx.fragment(
            knowledge_base_chat_component(_kb_chat_config), associated_resources_dialog()
        ),
    )


@rx.page(route="/", on_load=KnowledgeBaseChatState.load_new_chat_page)
def index():
    """Main chat page with sidebar (new conversation)."""
    return _chat_page_content()


@rx.page(route="/kb", on_load=KnowledgeBaseChatState.load_new_chat_page)
def knowledge_base_chat():
    """Same chat as ``/``, under the URL the shared knowledge-base state redirects to."""
    return _chat_page_content()


@rx.page(route="/chat/[conversation_id]", on_load=KnowledgeBaseChatState.load_conversation_from_url)
def chat_with_conversation():
    """Chat page for an existing conversation loaded from URL."""
    return _chat_page_content()


@rx.page(
    route="/kb/chat/[conversation_id]",
    on_load=KnowledgeBaseChatState.load_conversation_from_url,
)
def knowledge_base_chat_with_conversation():
    """Same conversation page as ``/chat/[conversation_id]``, under the ``/kb`` prefix."""
    return _chat_page_content()


# Chat profiles - list and edit page
@rx.page(route="/kb/chats", on_load=RagChatProfileListState.load_page)
def chat_profiles():
    """Chat profiles: create one, configure it, and bind the knowledge bases it searches."""
    return rag_page_layout_component(content=rag_chat_profile_list_component())


# Knowledge bases - list page
@rx.page(route="/kb/bases", on_load=KnowledgeBaseListState.load_knowledge_bases)
def knowledge_bases():
    """Knowledge-base manager: list, create and delete knowledge bases."""
    return rag_page_layout_component(content=knowledge_base_list_component())


# Knowledge bases - detail page
@rx.page(
    route="/kb/bases/[knowledge_base_id]",
    on_load=KnowledgeBaseDetailState.load_knowledge_base,
)
def knowledge_base_detail():
    """One knowledge base: its documents, their indexing status and the actions on them."""
    return rag_page_layout_component(content=knowledge_base_detail_component())


# AI Table configuration page
@rx.page(route="/config-ai-table")
def config_ai_table_page():
    """Configuration page for AI Table settings."""
    return rag_page_layout_component(content=ai_table_agent_chat_config_component())


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


# AI Table page - Excel/CSV-specific data analysis
@rx.page(route="/ai-table/[resource_id]", on_load=AiTableDataState.load_from_resource_id_url_param)
def ai_table():
    """AI Table page for Excel/CSV data analysis."""
    back_button = rx.tooltip(
        rx.link(
            rx.button(rx.icon("arrow-left", size=18), variant="ghost", size="2"),
            href="/",
            display="flex",
            align_items="center",
        ),
        content="Back to main page",
    )
    return main_component(
        rx.box(ai_table_component(header_left_component=back_button), height="100vh")
    )
