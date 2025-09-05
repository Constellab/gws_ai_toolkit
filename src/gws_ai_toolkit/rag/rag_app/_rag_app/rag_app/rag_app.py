
import reflex as rx
from gws_ai_toolkit.rag.rag_app._rag_app.rag_app.custom_ai_expert_component import \
    custom_left_sidebar
from gws_ai_toolkit.rag.rag_app._rag_app.rag_app.custom_ai_expert_state import \
    CustomAiExpertState
from gws_ai_toolkit.rag.rag_app._rag_app.rag_app.navigation import navigation
from gws_ai_toolkit.rag.rag_app._rag_app.rag_app.rag_main_state import \
    RagAppState
from gws_reflex_base import add_unauthorized_page, get_theme

from .reflex import (AppConfigState, ChatConfig, ConversationHistoryState,
                     HistoryState, RagConfigState, RagConfigStateConfig,
                     ai_expert_component, ai_expert_config_component,
                     ai_expert_header_default_buttons_component,
                     history_component, rag_chat_component,
                     rag_config_component)

app = rx.App(
    theme=get_theme(),
    stylesheets=["/style.css"],
)


def set_loader_from_param(param_name: str):
    """Set the loader function to get the config file path from a parameter."""
    async def loader(state: 'AppConfigState') -> str:
        base_state = await state.get_state(RagAppState)
        return await base_state.get_param(param_name)

    return loader


async def _load_config(state: rx.State) -> RagConfigStateConfig:
    """Load the RAG configuration."""
    base_state = await state.get_state(RagAppState)
    params = await base_state.get_params()
    return RagConfigStateConfig(
        rag_provider=params.get("rag_provider"),
        resource_sync_mode=params.get("resource_sync_mode"),
        dataset_id=params.get("dataset_id"),
        dataset_credentials_name=params.get("dataset_credentials_name"),
        chat_id=params.get("chat_id"),
        chat_credentials_name=params.get("chat_credentials_name"),
    )


# Chat page (index)
AppConfigState.set_loader(set_loader_from_param('configuration_file_path'))
ConversationHistoryState.set_loader(set_loader_from_param('history_file_path'))
RagConfigState.set_loader(_load_config)


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


def rag_chat_page() -> rx.Component:
    """RAG Chat page component."""

    return page_component(
        rag_chat_component()
    )


def ai_expert_page() -> rx.Component:
    """AI Expert page component for document-specific chat."""

    config = ChatConfig(
        state=CustomAiExpertState,
        header_buttons=ai_expert_header_default_buttons_component,
        left_section=custom_left_sidebar
    )
    return page_component(
        ai_expert_component(config)
    )


def history_page() -> rx.Component:
    """History page component."""
    return page_component(
        history_component()
    )


def rag_config_page() -> rx.Component:
    """RAG Configuration page component."""
    return page_component(
        rag_config_component()
    )


def ai_expert_config_page() -> rx.Component:
    """AI Expert Configuration page component."""
    return page_component(
        ai_expert_config_component()
    )


@rx.page(route="/")
def index():
    """Main chat page."""
    return rag_chat_page()


# Resource page - for resource and sync management
@rx.page(route="/rag-config")
def rag_config():
    """Resource page for managing RAG resources and sync."""
    return rag_config_page()


# Configuration page - for AI Expert configurations
@rx.page(route="/config")
def config_page():
    """Configuration page for AI Expert settings."""
    return ai_expert_config_page()


# History page - for conversation history
@rx.page(route="/history", on_load=HistoryState.load_conversations)
def history():
    """History page for viewing conversation history."""
    return history_page()


# AI Expert page - document-specific chat
@rx.page(route="/ai-expert/[rag_doc_id]", on_load=[CustomAiExpertState.load_resource_from_url])
def ai_expert():
    """AI Expert page for document-specific chat."""
    return ai_expert_page()


# Add the unauthorized page to the app.
# This page will be displayed if the user is not authenticated
add_unauthorized_page(app)
