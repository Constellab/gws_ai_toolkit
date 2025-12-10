import reflex as rx
import reflex_enterprise as rxe
from gws_ai_toolkit._app.ai_chat import (
    AppConfigState,
    ChatConfig,
    ConversationChatStateBase,
    HistoryState,
    NavBarItem,
    custom_sources_list_component,
    get_default_source_menu_items,
    history_component,
    page_component,
    source_message_component,
)
from gws_ai_toolkit._app.ai_rag import (
    AiExpertState,
    RagChatState,
    RagConfigState,
    RagConfigStateFromParams,
    ai_expert_component,
    ai_expert_header_default_buttons_component,
    rag_chat_component,
    rag_config_component,
)
from gws_ai_toolkit._app.ai_table import (
    AiTableDataState,
    ai_table_component,
)
from gws_ai_toolkit.models.chat.message.chat_message_source import RagChatSourceFront
from gws_reflex_main import register_gws_reflex_app

from .associated_resources_component import (
    associated_resources_dialog,
    associated_resources_section,
)
from .associated_resources_state import AssociatedResourcesState
from .config_page import combined_config_page
from .custom_states import CustomAppConfigState

AppConfigState.set_config_state_class_type(CustomAppConfigState)
RagConfigState.set_rag_config_state_class_type(RagConfigStateFromParams)

app = register_gws_reflex_app(rxe.App())

nav_bar_items: list[NavBarItem] = [
    NavBarItem(text="Chat", icon="message-circle", url="/"),
    NavBarItem(text="Resources", icon="database", url="/rag-config"),
    NavBarItem(text="Config", icon="settings", url="/config"),
    NavBarItem(text="History", icon="clock", url="/history"),
]


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


@rx.page(route="/")
def index():
    """Main chat page."""
    chat_config = ChatConfig(
        state=RagChatState,
        custom_chat_messages={
            "source": lambda message: source_message_component(
                message, RagChatState, sources_component_builder
            ),
        },
    )
    return page_component(
        nav_bar_items, rx.fragment(rag_chat_component(chat_config), associated_resources_dialog())
    )


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
    return page_component(
        nav_bar_items,
        rx.fragment(
            history_component(sources_component_builder=sources_component_builder),
            associated_resources_dialog(),
        ),
    )


# AI Expert page - document-specific chat
@rx.page(
    route="/ai-expert/[document_id]",
    on_load=[AiExpertState.load_resource_from_url, AssociatedResourcesState.load_from_expert_state],
)
def ai_expert():
    """AI Expert page for document-specific chat."""
    config = ChatConfig(
        state=AiExpertState,
        header_buttons=ai_expert_header_default_buttons_component,
        left_section=associated_resources_section,
    )
    return page_component(nav_bar_items, ai_expert_component(config))


# AI Table page - Excel/CSV-specific data analysis
# ça ne marche pas car dans l'app table, on Import the AppConfigState depuis gws_toolkit_ai ...
# Ce qui fait que c'est une autre instance que celle customisée ici
@rx.page(route="/ai-table/[resource_id]", on_load=AiTableDataState.load_from_resource_id_url_param)
def ai_table():
    """AI Table page for Excel/CSV data analysis."""
    return page_component(nav_bar_items, ai_table_component(), disable_padding=True)
