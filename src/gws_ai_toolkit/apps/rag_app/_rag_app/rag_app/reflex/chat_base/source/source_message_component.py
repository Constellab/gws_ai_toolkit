from collections.abc import Callable

import reflex as rx
from gws_ai_toolkit.models.chat.message.chat_message_source import (
    ChatMessageSourceFront,
    RagChatSourceFront,
)
from gws_reflex_main import extension_badge_component

from ..conversation_chat_state_base import ConversationChatStateBase
from .source_detail_state import SourceDetailState
from .source_menu_component import CustomSourceMenuButtons, resolve_source_menu_items

SourcesComponentBuilder = Callable[
    [list[RagChatSourceFront], ConversationChatStateBase], rx.Component
]

# JavaScript to handle clicks on source placeholders
source_click_script = """
{
    if(event && event.target && event.target.classList && event.target.classList.contains('source-placeholder')) {
        const sourceId = event.target.getAttribute('data-source-id');
        if(sourceId) {
            return sourceId;
        }
    }
    return null;
}
"""


def _source_item(
    source: RagChatSourceFront,
    state: ConversationChatStateBase,
    custom_menu_items: CustomSourceMenuButtons | None = None,
) -> rx.Component:
    """Individual source item styled as an inline pill badge with extension badge.

    Renders a single source citation with a colored file-extension badge
    and the document name, styled similarly to the SectionRef component
    in the JSX reference design.

    Args:
        source (RagChatSourceFront): Source citation with document metadata
        state (ConversationChatStateBase): Chat state for handling actions
        custom_menu_items: Optional callable that returns custom menu items for the source

    Returns:
        rx.Component: Formatted source pill with extension badge and document name
    """

    pill = rx.box(
        rx.hstack(
            extension_badge_component(source.document_extension),
            rx.text(
                source.document_name,
                size="1",
                weight="medium",
                trim="both",
            ),
            align_items="center",
            spacing="2",
        ),
        padding_x="10px",
        padding_y="6px",
        background="var(--accent-2)",
        border="1px solid var(--accent-6)",
        border_radius="var(--radius-2)",
        cursor="pointer",
        _hover={
            "background": "var(--accent-3)",
            "border_color": "var(--accent-7)",
        },
    )

    menu_items = resolve_source_menu_items(source, state, custom_menu_items)
    if menu_items:
        return rx.menu.root(
            rx.menu.trigger(pill),
            rx.menu.content(*menu_items),
        )

    return pill


def sources_list_component(
    sources: list[RagChatSourceFront],
    state: ConversationChatStateBase,
    custom_menu_items: CustomSourceMenuButtons | None = None,
) -> rx.Component:
    """Inline source badges for RAG chat responses.

    Displays source documents as inline pill badges with colored file-extension
    icons, styled after the SectionRef pattern in the JSX reference design.

    Features:
        - Inline pill badges with file-extension color coding
        - Action menu for each source (AI Expert, Open Document)
        - Horizontal flex-wrap layout
        - Conditional display (only shows when sources exist)

    Args:
        sources (List[RagChatSourceFront]): List of source citations from RAG response
        state (ConversationChatStateBase): Chat state for handling source interactions
        custom_menu_items: Optional callable that returns custom menu items for each source

    Returns:
        rx.Component: Flex-wrap container of source pill badges,
            or empty component if no sources provided.
    """
    return rx.cond(
        sources,
        rx.flex(
            rx.foreach(sources, lambda source: _source_item(source, state, custom_menu_items)),
            wrap="wrap",
            gap="2",
            margin_top="10px",
        ),
        rx.box(),
    )


def custom_sources_list_component(
    custom_menu_items: CustomSourceMenuButtons,
) -> SourcesComponentBuilder:
    """Wrapper for sources_list_component with custom menu items.

    This function allows users to create a sources list component
    with their own custom menu items for each source.

    Args:
        custom_menu_items: Callable that returns custom menu items for each source

    Returns:
        Callable[[List[RagChatSourceFront], ConversationChatStateBase], rx.Component]: A function that takes
        a list of sources and a chat state, and returns a sources list component.
    """
    return lambda sources, state: sources_list_component(sources, state, custom_menu_items)


def source_message_component(
    message: ChatMessageSourceFront,
    state: ConversationChatStateBase,
    custom_sources_component_builder: SourcesComponentBuilder | None = None,
) -> rx.Component:
    """Render ChatMessageSourceFront with clickable source buttons.

    Args:
        message: Frontend message with markdown content containing source placeholders
        state: Chat state for handling source button clicks

    Returns:
        rx.Component: Message with markdown text and clickable source buttons
    """
    return rx.box(
        rx.markdown(message.content, font_size="14px"),
        custom_sources_component_builder(message.sources, state)
        if custom_sources_component_builder
        else sources_list_component(message.sources, state),
        style={
            "& .source-placeholder": {
                "display": "inline-flex",
                "align-items": "center",
                "justify-content": "center",
                "background-color": "var(--accent-2)",
                "border": "2px solid var(--accent-10)",
                "color": "var(--accent-10)",
                "border-radius": "50%",
                "min-width": "18px",
                "height": "18px",
                "font-size": "12px",
                "font-weight": "bold",
                "cursor": "pointer",
                "margin-inline": "5px",
            },
            "& .source-placeholder:hover": {
                "opacity": "0.8",
            },
        },
        on_click=rx.run_script(
            source_click_script.strip().replace("\n", "").replace("    ", ""),
            callback=SourceDetailState.open_source_dialog,
        ),
    )
