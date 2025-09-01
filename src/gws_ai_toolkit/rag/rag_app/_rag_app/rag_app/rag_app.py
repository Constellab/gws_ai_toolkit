import reflex as rx
from gws_reflex_base import add_unauthorized_page, get_theme

from gws_ai_toolkit.rag.rag_app._rag_app.rag_app.components.app_config.app_config_state import \
    AppConfigState

from .pages.ai_expert_page.ai_expert_page import ai_expert_page
from .pages.ai_expert_page.ai_expert_state import AiExpertState
from .pages.chat_page.chat_page import chat_page
from .pages.config_page import config_page
from .pages.resource_page import resource_page

app = rx.App(
    theme=get_theme(),
    stylesheets=["/style.css"],
)


# Chat page (index)
AppConfigState.set_loader_from_param('configuration_file_path')


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


# AI Expert page - document-specific chat
# @rx.page(route="/ai-expert/[rag_doc_id]", on_load=[AiExpertState.load_resource_from_url])
# def ai_expert():
    """AI Expert page for document-specific chat."""
    # return ai_expert_page()


# Add the unauthorized page to the app.
# This page will be displayed if the user is not authenticated
add_unauthorized_page(app)
