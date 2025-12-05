import reflex as rx
import reflex_enterprise as rxe
from gws_ai_toolkit._app.ai_chat import (
    AppConfigState,
    NavBarItem,
    page_component,
)
from gws_reflex_main import register_gws_reflex_app
from gws_reflex_main.reflex_main_state import ReflexMainState

from .ai_table.ai_table_component import ai_table_component
from .ai_table.ai_table_data_state import AiTableDataState
from .ai_table.chat.table_agent.ai_table_agent_chat_config_component import (
    ai_table_agent_chat_config_component,
)
from .custom_states import CustomAppConfigState
from .home_page import home_page

AppConfigState.set_config_state_class_type(CustomAppConfigState)


app = register_gws_reflex_app(rxe.App())


class NavBarState(rx.State):
    @rx.var
    async def show_config_page(self) -> bool:
        """Determine if the Config page should be shown in the nav bar."""
        main_state = await self.get_state(ReflexMainState)
        show_config_page = await main_state.get_param("show_config_page", False)
        return show_config_page

    @rx.var
    async def nav_bar_items(self) -> list[NavBarItem]:
        nav_bar_items: list[NavBarItem] = [
            NavBarItem(text="Home", icon="home", url="/"),
            NavBarItem(text="AI Table", icon="message-circle", url="/ai-table"),
        ]

        show_config_page = await self.show_config_page
        if show_config_page:
            nav_bar_items.append(
                NavBarItem(text="Config", icon="settings", url="/config"),
            )
            nav_bar_items.append(
                NavBarItem(text="History", icon="clock", url="/history"),
            )

        return nav_bar_items


# Home page route (now at root)
@rx.page()
def index():
    """Home page for file upload"""
    return page_component(
        NavBarState.nav_bar_items,
        home_page(),
    )


# AI Table page


@rx.page(route="/ai-table")
def ai_table():
    # Render the main container with the app content.
    # The content will be displayed once the state is initialized.
    # If the state is not initialized, show message to go to home page.
    return page_component(
        NavBarState.nav_bar_items,
        rx.cond(
            AiTableDataState.dataframe_loaded,
            ai_table_component(),
            rx.center(
                rx.vstack(
                    rx.heading("No File Selected", size="6"),
                    rx.text(
                        "Please upload a file first to analyze your data.",
                        font_size="lg",
                        color="var(--gray-11)",
                        text_align="center",
                    ),
                    rx.button(
                        "Go to Home",
                        on_click=rx.redirect("/"),
                        size="3",
                    ),
                    align="center",
                    spacing="4",
                ),
                height="100%",
                width="100%",
            ),
        ),
        disable_padding=True,
    )


# Configuration page - for AI Expert and AI Table configurations


@rx.page(route="/config")
def config_page():
    """Configuration page for AI Expert and AI Table settings."""
    return rx.cond(
        NavBarState.show_config_page,
        page_component(
            NavBarState.nav_bar_items,
            ai_table_agent_chat_config_component(),
        ),
        rx.text("Configuration page is not available.", color="red"),
    )


# History page - for conversation history


# @rx.page(route="/history", on_load=HistoryState.load_conversations)
# def history():
#     """History page for viewing conversation history."""
#     return page_component(nav_bar_items, history_component())
