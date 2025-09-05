import reflex as rx
from gws_reflex_base import add_unauthorized_page, get_theme

from .config_page import combined_config_page
from .custom_ai_expert_component import custom_left_sidebar
from .custom_ai_expert_state import (CustomAssociatedResourceAiExpertState,
                                     CustomAssociatedResourceAiTableState)
# Import custom states to let reflex instantiate them
from .custom_states import (CustomAppConfigState,
                            CustomConversationHistoryState,
                            CustomRagConfigState)
from .navigation import navigation
from .reflex import (AiExpertState, AiTableState, ChatConfig, HistoryState,
                     ai_expert_component,
                     ai_expert_header_default_buttons_component,
                     ai_table_component, history_component, rag_chat_component,
                     rag_config_component)

app = rx.App(
    theme=get_theme(),
    stylesheets=["/style.css"],
)


def page_component(content: rx.Component) -> rx.Component:
    """Wrap the page content with navigation and layout."""
    return rx.vstack(
        navigation(),
        rx.box(
            content,
            display="flex",
            width="100%",
            flex="1",
            padding="1em",
            min_height="0",
        ),
        spacing="0",
        width="100%",
        height="100vh",
    )


@rx.page(route="/")
def index():
    """Main chat page."""
    return page_component(
        rag_chat_component()
    )


# Resource page - for resource and sync management
@rx.page(route="/rag-config")
def rag_config():
    """Resource page for managing RAG resources and sync."""
    return page_component(
        rag_config_component()
    )


# Configuration page - for AI Expert and AI Table configurations
@rx.page(route="/config")
def config_page():
    """Configuration page for AI Expert and AI Table settings."""
    return page_component(
        combined_config_page()
    )


# History page - for conversation history
@rx.page(route="/history", on_load=HistoryState.load_conversations)
def history():
    """History page for viewing conversation history."""
    return page_component(
        history_component()
    )


# AI Expert page - document-specific chat
@rx.page(route="/ai-expert/[object_id]", on_load=[AiExpertState.load_resource_from_url])
def ai_expert():
    """AI Expert page for document-specific chat."""
    config = ChatConfig(
        state=AiExpertState,
        header_buttons=ai_expert_header_default_buttons_component,
        left_section=lambda x: custom_left_sidebar(x, CustomAssociatedResourceAiExpertState)
    )
    return page_component(
        ai_expert_component(config)
    )


# AI Table page - Excel/CSV-specific data analysis
@rx.page(route="/ai-table/[object_id]")
def ai_table():
    """AI Table page for Excel/CSV data analysis."""
    config = ChatConfig(
        state=AiTableState,
        header_buttons=ai_expert_header_default_buttons_component,
        left_section=lambda x: custom_left_sidebar(x, CustomAssociatedResourceAiTableState)
    )
    return page_component(
        ai_table_component(config)
    )


# Add the unauthorized page to the app.
# This page will be displayed if the user is not authenticated
add_unauthorized_page(app)
