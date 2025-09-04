from typing import List

import reflex as rx

from gws_ai_toolkit.rag.common.rag_models import RagChatSource

from .chat_state_base import ChatStateBase


def _source_item(source: RagChatSource, state: ChatStateBase) -> rx.Component:
    """Individual source item with document info and action menu.
    
    Renders a single source citation with document name, relevance score,
    and dropdown menu for actions like opening in AI Expert or viewing
    the original document.
    
    Args:
        source (RagChatSource): Source citation with document metadata
        state (ChatStateBase): Chat state for handling actions
        
    Returns:
        rx.Component: Formatted source item with name, score, and actions menu
    """
    return rx.box(
        rx.hstack(
            rx.icon("file-text", size=16),
            rx.text(source.document_name, size="1",),
            rx.spacer(),
            rx.text(f"Score: {source.score:.2f}", size="1",),
            rx.menu.root(
                rx.menu.trigger(
                    rx.button(
                        rx.icon("ellipsis-vertical", size=16),
                        variant="ghost",
                        cursor='pointer'
                    )
                ),
                rx.menu.content(
                    rx.menu.item(
                        rx.icon("bot", size=16),
                        "Open AI Expert", on_click=lambda: state.open_ai_expert(source.document_id)
                    ),
                    rx.menu.item(
                        rx.icon("external-link", size=16),
                        "Open document", on_click=lambda: state.open_document(source.document_id)
                    ),
                ),
                flex_shrink="0"
            ),
            align_items="center",),
        padding="2",)


def sources_list_component(sources: List[RagChatSource], state: ChatStateBase) -> rx.Component:
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
        state (ChatStateBase): Chat state for handling source interactions
        
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
                        rx.foreach(sources, lambda source: _source_item(source, state)),
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
