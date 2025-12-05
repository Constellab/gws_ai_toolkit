"""Document browser component for selecting documents in AI Expert mode."""

import reflex as rx
from gws_ai_toolkit.apps.rag_app._rag_app.rag_app.reflex.ai_expert.ai_expert_state import (
    AiExpertState,
)
from gws_ai_toolkit.rag.common.rag_models import RagChatSource

from .document_browser_state import DocumentBrowserState


def document_row(source: RagChatSource) -> rx.Component:
    """Display a single document as a table row.

    Args:
        source: The RagChatSource containing document information

    Returns:
        rx.Component: A table row displaying the document with an open button
    """
    return rx.table.row(
        rx.table.cell(
            rx.hstack(
                rx.icon("file-text", size=18, color="var(--accent-9)"),
                rx.text(
                    source.document_name,
                    size="3",
                ),
                spacing="2",
                align="center",
            ),
        ),
        rx.table.cell(
            rx.button(
                "Open",
                on_click=lambda: rx.redirect(f"/ai-expert/{source.document_id}"),
                variant="soft",
                size="2",
            ),
            text_align="right",
        ),
    )


def empty_state_component() -> rx.Component:
    """Display when no documents are available.

    Returns:
        rx.Component: Empty state message
    """
    return rx.center(
        rx.vstack(
            rx.icon("file-x", size=48, color="var(--gray-9)"),
            rx.text(
                "No source documents found",
                size="5",
                weight="bold",
                color="var(--gray-11)",
            ),
            rx.text(
                "Source documents appear here when referenced in your chat conversations",
                size="3",
                color="var(--gray-10)",
            ),
            spacing="3",
            align="center",
        ),
        width="100%",
        height="400px",
    )


def document_browser_component() -> rx.Component:
    """Main document browser component for selecting documents.

    Displays a list of available documents from chat history that can be
    opened in AI Expert mode. Shows an empty state if no documents are available.

    Returns:
        rx.Component: The complete document browser interface
    """
    return rx.hstack(
        rx.box(flex="1"),  # Left spacer
        rx.box(
            rx.vstack(
                # Header
                rx.vstack(
                    rx.heading(AiExpertState.title, size="6"),
                    rx.text(
                        "Select a source document from your chat history to start an in-depth conversation",
                        size="3",
                        color="var(--gray-11)",
                    ),
                    spacing="2",
                    align="start",
                    width="100%",
                ),
                # Documents list or empty state
                rx.cond(
                    DocumentBrowserState.is_loading,
                    # Loading state
                    rx.center(
                        rx.spinner(size="3"),
                        width="100%",
                        height="400px",
                    ),
                    rx.cond(
                        DocumentBrowserState.has_documents,
                        # Documents table
                        rx.table.root(
                            rx.table.header(
                                rx.table.row(
                                    rx.table.column_header_cell("Document"),
                                    rx.table.column_header_cell("", text_align="right"),
                                ),
                            ),
                            rx.table.body(
                                rx.foreach(
                                    DocumentBrowserState.documents,
                                    document_row,
                                ),
                            ),
                            width="100%",
                            variant="surface",
                        ),
                        # Empty state
                        empty_state_component(),
                    ),
                ),
                spacing="6",
                align="start",
                width="100%",
            ),
            width="100%",
            max_width="800px",
        ),
        rx.box(flex="1"),  # Right spacer
        width="100%",
        align_items="stretch",
    )
