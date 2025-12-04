from collections.abc import Callable

import reflex as rx
from gws_ai_toolkit.rag.common.rag_models import RagChatSource

from .conversation_chat_state_base import ConversationChatStateBase

SourcesComponentBuilder = Callable[
    [list[RagChatSource] | None, ConversationChatStateBase], rx.Component
]


def get_default_source_menu_items(
    source: RagChatSource, state: ConversationChatStateBase
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


def _source_item(
    source: RagChatSource,
    state: ConversationChatStateBase,
    custom_menu_items: Callable[[RagChatSource, ConversationChatStateBase], list[rx.Component]]
    | None = None,
) -> rx.Component:
    """Individual source item with document info and action menu.

    Renders a single source citation with document name, relevance score,
    and dropdown menu for actions like opening in AI Expert or viewing
    the original document.

    Args:
        source (RagChatSource): Source citation with document metadata
        state (ConversationChatStateBase): Chat state for handling actions
        custom_menu_items: Optional callable that returns custom menu items for the source

    Returns:
        rx.Component: Formatted source item with name, score, and actions menu
    """

    # Get menu items based on custom_menu_items parameter
    menu_items: list[rx.Component] = []
    if custom_menu_items is None:
        # Use default menu items
        menu_items = get_default_source_menu_items(source, state)
    elif custom_menu_items is not None:
        # Call the custom menu items function
        menu_items = custom_menu_items(source, state)

    # Build the base hstack items
    hstack_items = [
        rx.icon("file-text", size=16),
        rx.text(
            source.document_name,
            size="1",
        ),
        rx.spacer(),
        rx.text(
            f"Score: {source.score:.2f}",
            size="1",
        ),
    ]

    # Only add menu if there are menu items
    if menu_items and len(menu_items) > 0:
        menu_root = rx.menu.root(
            rx.menu.trigger(
                rx.button(rx.icon("ellipsis-vertical", size=16), variant="ghost", cursor="pointer")
            ),
            rx.menu.content(*menu_items),
            flex_shrink="0",
        )
        hstack_items.append(menu_root)

    return rx.box(
        rx.hstack(
            *hstack_items,
            align_items="center",
        ),
        padding="2",
    )


def sources_list_component(
    sources: list[RagChatSource] | None,
    state: ConversationChatStateBase,
    custom_menu_items: Callable[[RagChatSource, ConversationChatStateBase], list[rx.Component]]
    | None = None,
) -> rx.Component:
    """Expandable sources panel for RAG chat responses.

    This component displays source documents and citations for RAG-enhanced
    chat responses, providing users with transparency about the information
    sources and enabling navigation to source documents or AI Expert analysis.

    Features:
        - Expandable accordion interface for space efficiency
        - Source document names and relevance scores
        - Action menu for each source (AI Expert, Open Document)
        - Professional styling with icons and proper spacing
        - Conditional display (only shows when sources exist)

    Args:
        sources (List[RagChatSource]): List of source citations from RAG response
        state (ConversationChatStateBase): Chat state for handling source interactions

    Returns:
        rx.Component: Conditional accordion component displaying sources with
            action menus, or empty component if no sources provided.

    Example:
        sources_panel = sources_list_component(rag_sources, chat_state)
        # Shows expandable "Sources" section with clickable source items
    """
    return rx.cond(
        sources,
        rx.accordion.root(
            rx.accordion.item(
                header="Sources",
                content=rx.accordion.content(
                    rx.vstack(
                        rx.foreach(
                            sources, lambda source: _source_item(source, state, custom_menu_items)
                        ),
                        spacing="2",
                        align="stretch",
                    ),
                ),
                value="sources",
            ),
            collapsible=True,
            width="100%",
            variant="soft",
        ),
    )


def custom_sources_list_component(
    custom_menu_items: Callable[[RagChatSource, ConversationChatStateBase], list[rx.Component]],
) -> SourcesComponentBuilder:
    """Wrapper for sources_list_component with custom menu items.

    This function allows users to create a sources list component
    with their own custom menu items for each source.

    Args:
        custom_menu_items: Callable that returns custom menu items for each source

    Returns:
        Callable[[List[RagChatSource], ConversationChatStateBase], rx.Component]: A function that takes
        a list of sources and a chat state, and returns a sources list component.
    """
    return lambda sources, state: sources_list_component(sources, state, custom_menu_items)
