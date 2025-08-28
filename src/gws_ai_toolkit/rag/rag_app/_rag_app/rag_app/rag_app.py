import reflex as rx
from gws_reflex_base import add_unauthorized_page, get_theme
from gws_reflex_main import ReflexMainState

from .pages.ai_expert_page.ai_expert_page import ai_expert_page
from .pages.ai_expert_page.ai_expert_state import AiExpertState
from .pages.chat_page.chat_page import chat_page
from .pages.config_page import config_page

app = rx.App(
    theme=get_theme(),
)


# Chat page (index)
@rx.page(route="/", on_load=ReflexMainState.on_load)
def index():
    """Main chat page."""
    return chat_page()


# Configuration page - only show if enabled in params
@rx.page(route="/config", on_load=ReflexMainState.on_load)
def config():
    """Configuration page for managing RAG resources."""
    return config_page()


# AI Expert page - document-specific chat
@rx.page(route="/ai-expert/[rag_doc_id]", on_load=[ReflexMainState.on_load, AiExpertState.load_resource_from_url])
def ai_expert():
    """AI Expert page for document-specific chat."""
    return ai_expert_page()


# Add the unauthorized page to the app.
# This page will be displayed if the user is not authenticated
add_unauthorized_page(app)
