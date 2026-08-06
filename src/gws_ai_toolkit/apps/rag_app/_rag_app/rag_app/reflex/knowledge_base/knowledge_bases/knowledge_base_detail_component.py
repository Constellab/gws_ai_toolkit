"""The detail page of one knowledge base: what it is, what is in it, and how indexing went.

The header carries the facts that decide what a retrieval will return — the instance scope (which
vector space holds the chunks) and the chunking policy — because they are not editable from here and a
user needs to know them before wondering why an answer is what it is. Its name and description *are*
editable from here, behind the same actions menu the list page uses; ``KnowledgeBaseListState`` owns
that dialog and the delete confirmation, so ``knowledge_base_edit_dialog`` has to be rendered on this
page too for either to be able to show.
"""

import reflex as rx

from ..core.summary_item_component import summary_item
from .add_document_dialog.add_document_dialog_component import add_document_button
from .document_table_component import document_table_component
from .knowledge_base_actions_menu_component import knowledge_base_actions_menu
from .knowledge_base_detail_state import KnowledgeBaseDetailState
from .knowledge_base_list_component import knowledge_base_edit_dialog
from .knowledge_base_list_state import KNOWLEDGE_BASES_ROUTE


def knowledge_base_detail_component() -> rx.Component:
    """The knowledge-base detail page."""
    return rx.vstack(
        _breadcrumb(),
        rx.cond(
            KnowledgeBaseDetailState.knowledge_base,
            rx.vstack(
                _header(),
                _summary(),
                rx.divider(),
                _documents_section(),
                spacing="4",
                width="100%",
            ),
            _not_found_message(),
        ),
        knowledge_base_edit_dialog(),
        spacing="4",
        padding="1em",
        width="100%",
    )


def _breadcrumb() -> rx.Component:
    """The way back to the list."""
    return rx.button(
        rx.icon("arrow-left", size=16),
        "Knowledge bases",
        variant="ghost",
        size="2",
        on_click=rx.redirect(KNOWLEDGE_BASES_ROUTE),
    )


def _header() -> rx.Component:
    """Name, description, and the two structural facts about the knowledge base."""
    return rx.vstack(
        rx.hstack(
            rx.heading(KnowledgeBaseDetailState.knowledge_base.name, size="7"),
            rx.spacer(),
            add_document_button(),
            knowledge_base_actions_menu(KnowledgeBaseDetailState.knowledge_base, icon_size=22),
            align="center",
            width="100%",
        ),
        rx.cond(
            KnowledgeBaseDetailState.knowledge_base.description,
            rx.text(
                KnowledgeBaseDetailState.knowledge_base.description,
                size="2",
                color="var(--gray-11)",
            ),
        ),
        spacing="2",
        width="100%",
    )


def _summary() -> rx.Component:
    """Documents, chunks, instance scope and chunking policy."""
    return rx.hstack(
        summary_item("file-text", KnowledgeBaseDetailState.document_count.to_string(), "documents"),
        summary_item("layers", KnowledgeBaseDetailState.total_chunk_count.to_string(), "chunks"),
        summary_item(
            "database", KnowledgeBaseDetailState.knowledge_base.instance_scope, "instance scope"
        ),
        summary_item("scissors", KnowledgeBaseDetailState.chunk_config_label, "chunking"),
        spacing="5",
        wrap="wrap",
        width="100%",
    )


def _documents_section() -> rx.Component:
    """The document table, its refresh button and the indexing indicator."""
    return rx.vstack(
        rx.hstack(
            rx.heading("Documents", size="5"),
            rx.cond(
                KnowledgeBaseDetailState.is_indexing,
                rx.hstack(
                    rx.spinner(size="1"),
                    rx.text("Indexing...", size="2", color="var(--gray-11)"),
                    align="center",
                    spacing="2",
                ),
            ),
            rx.spacer(),
            rx.button(
                rx.icon("refresh-cw", size=16),
                "Refresh",
                variant="soft",
                on_click=KnowledgeBaseDetailState.refresh_documents,
                loading=KnowledgeBaseDetailState.is_loading,
            ),
            align="center",
            width="100%",
        ),
        document_table_component(),
        spacing="3",
        width="100%",
    )


def _not_found_message() -> rx.Component:
    """What the page says when the route names a knowledge base that is not there."""
    return rx.cond(
        KnowledgeBaseDetailState.is_loading,
        rx.center(rx.spinner(size="3"), width="100%", padding="3rem"),
        rx.vstack(
            rx.icon("circle-alert", size=28, color="var(--gray-8)"),
            rx.text("This knowledge base does not exist.", size="2", weight="medium"),
            rx.button(
                "Back to knowledge bases",
                on_click=rx.redirect(KNOWLEDGE_BASES_ROUTE),
            ),
            align="center",
            spacing="3",
            width="100%",
            padding="3rem 1rem",
        ),
    )
