import reflex as rx
from gws_ai_toolkit._app.ai_chat import (
    AppConfigState,
    ConversationChatStateBase,
    custom_sources_list_component,
    get_default_source_menu_items,
    source_message_component,
)
from gws_ai_toolkit._app.ai_rag import (
    AdminHistoryState,
    RagChatConfigState,
    RagChatState,
    RagConfigState,
    RagConfigStateFromParams,
    admin_history_detail_component,
    admin_history_list_component,
    rag_chat_component,
    rag_chat_config_component,
    rag_chat_config_factory,
    rag_config_component,
    rag_page_layout_component,
)
from gws_ai_toolkit._app.ai_table import (
    AiTableDataState,
    ai_table_agent_chat_config_component,
    ai_table_component,
)
from gws_ai_toolkit.models.chat.message.chat_message_source import (
    ChatMessageSourceFront,
    RagChatSourceFront,
)
from gws_reflex_main import ReflexDownloadService, main_component, register_gws_reflex_app

from .associated_resources_component import associated_resources_dialog
from .associated_resources_state import AssociatedResourcesState
from .custom_states import CustomAppConfigState

AppConfigState.set_config_state_class_type(CustomAppConfigState)
RagConfigState.set_rag_config_state_class_type(RagConfigStateFromParams)

# Theme is configured via RadixThemesPlugin in rxconfig.py (App(theme=...) is
# deprecated), so the app is created without an explicit theme here.
app = register_gws_reflex_app(rx.App())

# Serves knowledge-base document snapshots over HTTP: a 15 MB file pushed through the websocket event
# channel would freeze the UI while it travels. Required by ``build_open_document_event``.
app.api_transformer = ReflexDownloadService.build_api()


def custom_source_menu_items(source: RagChatSourceFront, state: ConversationChatStateBase):
    items = get_default_source_menu_items(source, state)
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


sources_component_builder = custom_sources_list_component(custom_source_menu_items)

_rag_chat_config = rag_chat_config_factory(
    custom_chat_messages={
        "source": (
            ChatMessageSourceFront,
            lambda message: source_message_component(
                message, RagChatState, sources_component_builder
            ),
        ),
    },
)


@rx.page(route="/")
def index():
    """Main chat page with sidebar (new conversation)."""
    return rag_page_layout_component(
        content=rx.fragment(rag_chat_component(_rag_chat_config), associated_resources_dialog()),
    )


@rx.page(route="/chat/[conversation_id]", on_load=RagChatState.load_conversation_from_url)
def chat_with_conversation():
    """Chat page for an existing conversation loaded from URL."""
    return rag_page_layout_component(
        content=rx.fragment(rag_chat_component(_rag_chat_config), associated_resources_dialog()),
    )


# Resource page - for resource and sync management
@rx.page(route="/rag-config")
def rag_config():
    """Resource page for managing RAG resources and sync."""
    return rx.cond(
        RagChatConfigState.show_settings_menu,
        rag_page_layout_component(content=rag_config_component()),
        rx.text("RAG Config page is not available.", color="red"),
    )


# RAG Chat configuration page
@rx.page(route="/config-rag")
def config_rag_page():
    """Configuration page for RAG Chat settings."""
    return rx.cond(
        RagChatConfigState.show_settings_menu,
        rag_page_layout_component(content=rag_chat_config_component()),
        rx.text("Configuration page is not available.", color="red"),
    )


# AI Table configuration page
@rx.page(route="/config-ai-table")
def config_ai_table_page():
    """Configuration page for AI Table settings."""
    return rx.cond(
        RagChatConfigState.show_settings_menu,
        rag_page_layout_component(content=ai_table_agent_chat_config_component()),
        rx.text("Configuration page is not available.", color="red"),
    )


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
