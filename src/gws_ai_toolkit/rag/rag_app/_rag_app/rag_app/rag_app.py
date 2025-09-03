import reflex as rx
from gws_reflex_base import add_unauthorized_page, get_theme
from gws_reflex_main import ReflexMainState

from gws_ai_toolkit.rag.rag_app._rag_app.rag_app.reflex.core.app_config_state import \
    AppConfigState
from gws_ai_toolkit.rag.rag_app._rag_app.rag_app.reflex.history.conversation_history_state import \
    ConversationHistoryState
from gws_ai_toolkit.rag.rag_app._rag_app.rag_app.reflex.rag_chat.config.rag_config_state import (
    RagConfigState, RagConfigStateConfig)
from gws_ai_toolkit.rag.rag_app._rag_app.rag_app.states.rag_main_state import \
    RagAppState

from .pages.ai_expert_page.ai_expert_page import ai_expert_page
from .pages.ai_expert_page.ai_expert_state import AiExpertState
from .pages.chat_page.chat_page import chat_page
from .pages.config_page import config_page
from .pages.history_page.history_page import history_page
from .pages.history_page.history_page_state import HistoryPageState
from .pages.resource_page import resource_page

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
        dataset_id=params.get("dataset_id"),
        resource_sync_mode=params.get("resource_sync_mode"),
        credentials_name=params.get("dataset_credentials_name"),
    )


# Chat page (index)
AppConfigState.set_loader(set_loader_from_param('configuration_file_path'))
ConversationHistoryState.set_loader(set_loader_from_param('history_file_path'))
RagConfigState.set_loader(_load_config)


@rx.page(route="/")
def index():
    """Main chat page."""
    return chat_page()


# Resource page - for resource and sync management
@rx.page(route="/resource")
def resource():
    """Resource page for managing RAG resources and sync."""
    return resource_page()


# Configuration page - for AI Expert configurations
@rx.page(route="/config")
def config():
    """Configuration page for AI Expert settings."""
    return config_page()


# History page - for conversation history
@rx.page(route="/history", on_load=HistoryPageState.load_conversations)
def history():
    """History page for viewing conversation history."""
    return history_page()


# AI Expert page - document-specific chat
@rx.page(route="/ai-expert/[rag_doc_id]", on_load=[AiExpertState.load_resource_from_url])
def ai_expert():
    """AI Expert page for document-specific chat."""
    return ai_expert_page()


# Add the unauthorized page to the app.
# This page will be displayed if the user is not authenticated
add_unauthorized_page(app)
