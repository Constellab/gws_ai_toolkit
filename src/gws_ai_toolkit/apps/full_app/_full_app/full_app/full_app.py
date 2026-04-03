import reflex as rx
import reflex_enterprise as rxe
from gws_ai_toolkit._app.ai_chat import (
    AppConfigState,
    ConversationChatStateBase,
    custom_sources_list_component,
    get_default_source_menu_items,
    source_message_component,
)
from gws_ai_toolkit._app.ai_rag import (
    AdminHistoryState,
    AiExpertConfigState,
    AiExpertState,
    DocumentBrowserState,
    RagChatConfigState,
    RagChatState,
    RagConfigState,
    RagConfigStateFromParams,
    admin_history_detail_component,
    admin_history_list_component,
    ai_expert_chat_config_factory,
    ai_expert_config_component,
    ai_expert_page_content,
    document_browser_component,
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
from gws_reflex_main import get_theme, main_component, register_gws_reflex_app

from .associated_resources_component import (
    associated_resources_dialog,
    associated_resources_section,
)
from .associated_resources_state import AssociatedResourcesState
from .custom_states import CustomAppConfigState

AppConfigState.set_config_state_class_type(CustomAppConfigState)
RagConfigState.set_rag_config_state_class_type(RagConfigStateFromParams)

app = register_gws_reflex_app(rxe.App(theme=get_theme()))


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


# AI Expert configuration page
@rx.page(route="/config-ai-expert")
def config_ai_expert_page():
    """Configuration page for AI Expert settings."""
    return rx.cond(
        AiExpertConfigState.show_settings_menu,
        rag_page_layout_component(content=ai_expert_config_component()),
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


# AI Expert page - document browser (no document selected)
@rx.page(
    route="/ai-expert",
    on_load=DocumentBrowserState.load_documents,
)
def ai_expert_browser():
    """AI Expert page for selecting a document."""
    return rag_page_layout_component(
        content=document_browser_component(),
    )


ai_expert_chat_conf = ai_expert_chat_config_factory(left_section=associated_resources_section)


# AI Expert page - existing conversation loaded from URL
@rx.page(
    route="/ai-expert/chat/[conversation_id]",
    on_load=[
        AiExpertState.load_conversation_from_url,
        AssociatedResourcesState.load_from_expert_state,
    ],
)
def ai_expert_with_conversation():
    """AI Expert page for an existing conversation loaded from URL."""
    return ai_expert_page_content(ai_expert_chat_conf)


# AI Expert page - document-specific chat (new conversation)
@rx.page(
    route="/ai-expert/[document_id]",
    on_load=[AiExpertState.load_resource_from_url, AssociatedResourcesState.load_from_expert_state],
)
def ai_expert():
    """AI Expert page for document-specific chat."""
    return ai_expert_page_content(ai_expert_chat_conf)


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
