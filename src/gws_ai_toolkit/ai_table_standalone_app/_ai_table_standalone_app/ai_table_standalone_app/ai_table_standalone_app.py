
from typing import List

import reflex as rx
import reflex_enterprise as rxe
from gws_reflex_base import add_unauthorized_page, get_theme

from gws_ai_toolkit._app.ai_table import ai_table_chat_config_component
from gws_ai_toolkit._app.core import NavBarItem, page_component
from gws_ai_toolkit._app.history import HistoryState, history_component

from .ai_table.ai_table_component import ai_table_component
from .ai_table.ai_table_data_state import AiTableDataState
# keep import to configure the states
from .custom_states import CustomAppConfigState, CustomConversationHistoryState
from .upload_section import upload_section

app = rxe.App(
    theme=get_theme()
)

nav_bar_items: List[NavBarItem] = [
    NavBarItem(text="AI Table", icon="message-circle", url="/"),
    NavBarItem(text="Config", icon="settings", url="/config"),
    NavBarItem(text="History", icon="clock", url="/history"),
]


# Declare the page and init the main state
@rx.page()
def index():
    # Render the main container with the app content.
    # The content will be displayed once the state is initialized.
    # If the state is not initialized, a loading spinner will be shown.
    return page_component(
        nav_bar_items,
        rx.cond(
            AiTableDataState.dataframe_loaded,
            ai_table_component(),
            upload_section(),
        ),
        disable_padding=True
    )

# Configuration page - for AI Expert and AI Table configurations


@rx.page(route="/config")
def config_page():
    """Configuration page for AI Expert and AI Table settings."""
    return page_component(
        nav_bar_items,
        ai_table_chat_config_component(),
    )

# History page - for conversation history


@rx.page(route="/history", on_load=HistoryState.load_conversations)
def history():
    """History page for viewing conversation history."""
    return page_component(
        nav_bar_items,
        history_component(CustomConversationHistoryState)
    )


# Add the unauthorized page to the app.
# This page will be displayed if the user is not authenticated
add_unauthorized_page(app)
