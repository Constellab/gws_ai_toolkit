
from typing import List

import reflex as rx
import reflex_enterprise as rxe
from gws_reflex_base import add_unauthorized_page, get_theme
from gws_reflex_main import ReflexMainState

from gws_ai_toolkit._ai_table import (AppConfigState, ConversationHistoryState,
                                      NavBarItem, ai_table_component,
                                      page_component)

app = rxe.App(
    theme=get_theme()
)

nav_bar_items: List[NavBarItem] = [
    NavBarItem(text="AI Table", icon="message-circle", url="/"),
    NavBarItem(text="Config", icon="settings", url="/config"),
]


class MainState(ReflexMainState, rx.State):
    """Main state define to access methods from ReflexMainState."""


class CustomAppConfigState(AppConfigState, rx.State):

    async def _get_config_file_path(self) -> str:
        base_state = await self.get_state(MainState)
        config = await base_state.get_param('configuration_file_path')
        return config or ''


class CustomConversationHistoryState(ConversationHistoryState, rx.State):

    async def _get_history_folder_path_param(self) -> str:
        base_state = await self.get_state(MainState)
        config = await base_state.get_param('history_folder_path')
        return config or ''


# Declare the page and init the main state
@rx.page()
def index():
    # Render the main container with the app content.
    # The content will be displayed once the state is initialized.
    # If the state is not initialized, a loading spinner will be shown.
    return page_component(
        nav_bar_items,
        ai_table_component(),
        disable_padding=True
    )

# Configuration page - for AI Expert and AI Table configurations


@rx.page(route="/config")
def config_page():
    """Configuration page for AI Expert and AI Table settings."""
    return page_component(
        nav_bar_items,
        rx.text("Configuration Page - Coming Soon!"),
    )


# Add the unauthorized page to the app.
# This page will be displayed if the user is not authenticated
add_unauthorized_page(app)
