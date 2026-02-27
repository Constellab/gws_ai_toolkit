from collections.abc import Callable

import reflex as rx
from gws_ai_toolkit.models.chat.message.chat_message_source import (
    RagChatSourceFront,
)

from ..conversation_chat_state_base import ConversationChatStateBase

CustomSourceMenuButtons = Callable[
    [RagChatSourceFront, ConversationChatStateBase], list[rx.Component]
]


def get_default_source_menu_items(
    source: RagChatSourceFront, state: ConversationChatStateBase
) -> list[rx.Component]:
    """Get the default menu items for source actions.

    Returns:
        List[rx.Component]: List of default menu items for source actions.
    """
    return [
        rx.menu.item(
            rx.icon("bot", size=16),
            "Open AI Expert",
            on_click=lambda: state.open_ai_expert(source.document_id),
        ),
        rx.menu.item(
            rx.icon("external-link", size=16),
            "Open document",
            on_click=lambda: state.open_document(source.document_id),
        ),
    ]


def resolve_source_menu_items(
    source: RagChatSourceFront,
    state: ConversationChatStateBase,
    custom_menu_items: CustomSourceMenuButtons | None = None,
) -> list[rx.Component]:
    """Resolve the menu items for a source, using custom or default items.

    Args:
        source (RagChatSourceFront): The source data.
        state (ConversationChatStateBase): The chat state.
        custom_menu_items (Callable, optional): Function to get custom menu items.

    Returns:
        list[rx.Component]: Resolved list of menu item components.
    """
    if custom_menu_items is not None:
        return custom_menu_items(source, state)
    return get_default_source_menu_items(source, state)


def source_menu_button(
    source: RagChatSourceFront,
    state: ConversationChatStateBase,
    custom_menu_items: CustomSourceMenuButtons | None = None,
) -> rx.Component | None:
    """Menu button for source actions.

    Renders a menu button with default and custom actions for a source.

    Args:
        source (RagChatSourceFront): The source data.
        state (ConversationChatStateBase): The chat state.
        custom_menu_items (Callable, optional): Function to get custom menu items.

    Returns:
        rx.Component: Menu button component with actions.
    """
    menu_items = resolve_source_menu_items(source, state, custom_menu_items)

    if menu_items and len(menu_items) > 0:
        return rx.menu.root(
            rx.menu.trigger(
                rx.button(rx.icon("ellipsis-vertical", size=16), variant="ghost", cursor="pointer")
            ),
            rx.menu.content(*menu_items),
            flex_shrink="0",
        )

    return None
