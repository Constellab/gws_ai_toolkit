import reflex as rx
from gws_reflex_base import add_unauthorized_page, get_theme
from gws_reflex_main import ReflexMainState

from .pages.chat_page import chat_page
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


# Add the unauthorized page to the app.
# This page will be displayed if the user is not authenticated
add_unauthorized_page(app)
