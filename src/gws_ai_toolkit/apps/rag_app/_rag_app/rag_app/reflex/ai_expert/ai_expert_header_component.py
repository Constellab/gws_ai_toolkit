import reflex as rx
from gws_ai_toolkit.models.chat.conversation.base_chat_conversation import ChatConversationMode
from gws_reflex_main import left_sidebar_open_button

from ..admin_history.admin_history_state import AdminHistoryState
from ..core.conversation_mode_chip_component import conversation_mode_chip_switchable


def _header_divider() -> rx.Component:
    """A vertical divider line for the header."""
    return rx.box(
        width="1px",
        height="24px",
        background="var(--gray-5)",
    )


def _ai_expert_settings_button(show_settings: rx.Var[bool]) -> rx.Component:
    """Settings menu button for AI Expert header with links to Resources, Config, and Admin History pages.

    :param show_settings: Reactive var controlling visibility.
    """
    return rx.cond(
        show_settings,
        rx.menu.root(
            rx.menu.trigger(
                rx.button(
                    rx.icon("settings", size=16),
                    variant="ghost",
                    size="2",
                    cursor="pointer",
                    color="var(--gray-11)",
                ),
            ),
            rx.menu.content(
                rx.menu.item(
                    rx.icon("database", size=16),
                    "Resources",
                    on_click=rx.redirect("/rag-config"),
                ),
                rx.menu.item(
                    rx.icon("settings", size=16),
                    "Config",
                    on_click=rx.redirect("/config-ai-expert"),
                ),
                rx.cond(
                    AdminHistoryState.show_admin_history,
                    rx.menu.item(
                        rx.icon("users", size=16),
                        "Admin History",
                        on_click=rx.redirect("/admin-history"),
                    ),
                ),
            ),
        ),
    )


def ai_expert_header_component(
    subtitle: rx.Var[str | None],
    on_view_document: rx.EventChain,
    show_settings: rx.Var[bool] | None = None,
) -> rx.Component:
    """Header for AI Expert pages showing the mode, document name, and view button.

    :param subtitle: Reactive var with the document/resource name.
    :param on_view_document: Event handler for the "View document" button.
    :param show_settings: Reactive var controlling settings button visibility.
    :return: The header component.
    """
    return rx.hstack(
        left_sidebar_open_button(),
        conversation_mode_chip_switchable(ChatConversationMode.AI_EXPERT.value, size="big"),
        _header_divider(),
        rx.cond(
            subtitle,
            rx.badge(
                rx.icon("file-text", size=14),
                rx.text(subtitle, size="2", weight="medium"),
                rx.icon(
                    "x",
                    size=14,
                    cursor="pointer",
                    _hover={"opacity": "0.7"},
                    on_click=rx.redirect("/ai-expert"),
                ),
                variant="soft",
                size="2",
                background="var(--gray-3)",
                color="var(--gray-12)",
            ),
            rx.text("Loading...", size="2", color="var(--gray-8)"),
        ),
        rx.spacer(),
        rx.button(
            rx.icon("eye", size=14),
            "View document",
            on_click=on_view_document,
            variant="solid",
            size="2",
        ),
        _ai_expert_settings_button(show_settings) if show_settings is not None else rx.fragment(),
        align="center",
        spacing="3",
        width="100%",
    )


def ai_expert_browser_header_component(show_settings: rx.Var[bool] | None = None) -> rx.Component:
    """Header for the AI Expert document browser page (no document selected).

    Shows the switchable AI Expert chip and the settings button.

    :param show_settings: Reactive var controlling settings button visibility.
    :return: The header component.
    """
    return rx.hstack(
        left_sidebar_open_button(),
        conversation_mode_chip_switchable(ChatConversationMode.AI_EXPERT.value, size="big"),
        _header_divider(),
        rx.text("Select a document", size="2", color="var(--gray-9)"),
        rx.spacer(),
        _ai_expert_settings_button(show_settings) if show_settings is not None else rx.fragment(),
        align="center",
        spacing="3",
        width="100%",
    )
