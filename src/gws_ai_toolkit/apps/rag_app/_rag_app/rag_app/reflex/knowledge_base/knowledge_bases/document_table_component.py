"""The document table of a knowledge base, and the chips that make its rows honest.

The status chip is the interesting part. ``KnowledgeBaseDocument.to_dto()`` already turns an over-age
indexing lease into ``error`` carrying ``INTERRUPTED_INDEXING_MESSAGE``, so this file needs no lease
logic of its own — it only has to *say* "interrupted" rather than "error" for that one message, and
offer the retry. A document genuinely being indexed right now still gets a spinner; what must never
happen is a spinner that spins forever because the run behind it died.

Per-row actions are deliberately three, not one menu: re-index reads the stored snapshot, refresh
re-fetches from the source system, and they are not interchangeable. An upload cannot be refreshed at
all, and says so when asked.
"""

import reflex as rx
from gws_ai_toolkit.models.knowledge_base.knowledge_base_document import (
    INTERRUPTED_INDEXING_MESSAGE,
)
from gws_ai_toolkit.models.knowledge_base.knowledge_base_dto import (
    DocumentIndexStatus,
    KnowledgeBaseDocumentDTO,
)

from .knowledge_base_detail_state import KnowledgeBaseDetailState


def document_table_component() -> rx.Component:
    """The documents of the loaded knowledge base, or a prompt to add the first one."""
    return rx.cond(
        KnowledgeBaseDetailState.has_documents,
        rx.box(
            rx.table.root(
                rx.table.header(
                    rx.table.row(
                        rx.table.column_header_cell("Document"),
                        rx.table.column_header_cell("Source"),
                        rx.table.column_header_cell("Status"),
                        rx.table.column_header_cell("Chunks"),
                        rx.table.column_header_cell("Indexed"),
                        rx.table.column_header_cell(""),
                    )
                ),
                rx.table.body(
                    rx.foreach(KnowledgeBaseDetailState.documents, _document_row),
                ),
                variant="surface",
                width="100%",
            ),
            width="100%",
            overflow_x="auto",
        ),
        _empty_documents_message(),
    )


def _empty_documents_message() -> rx.Component:
    """What an empty knowledge base says for itself."""
    return rx.vstack(
        rx.icon("file-text", size=28, color="var(--gray-8)"),
        rx.text("No documents yet.", size="2", weight="medium"),
        rx.text(
            "Add a document to have it indexed and searchable.",
            size="2",
            color="var(--gray-11)",
        ),
        align="center",
        justify="center",
        spacing="2",
        width="100%",
        padding="3rem 1rem",
    )


def _document_row(document: KnowledgeBaseDocumentDTO) -> rx.Component:
    """One document: what it is, where it came from, how its indexing went, what can be done to it."""
    return rx.table.row(
        rx.table.cell(
            rx.hstack(
                rx.text(document.filename, size="2", weight="medium"),
                _error_tooltip(document),
                align="center",
                spacing="2",
            )
        ),
        rx.table.cell(_source_type_chip(document)),
        rx.table.cell(_status_chip(document)),
        rx.table.cell(rx.text(document.chunk_count.to_string(), size="2")),
        rx.table.cell(
            rx.cond(
                document.indexed_at,
                rx.moment(document.indexed_at, from_now=True),
                rx.text("—", size="2", color="var(--gray-9)"),
            )
        ),
        rx.table.cell(_row_actions(document)),
        align="center",
    )


def _source_type_chip(document: KnowledgeBaseDocumentDTO) -> rx.Component:
    """Where the document came from — the provider key stored on the row."""
    return rx.badge(document.source_type, variant="soft", color_scheme="gray")


def _status_chip(document: KnowledgeBaseDocumentDTO) -> rx.Component:
    """The indexing status, with a reclaimed or expired lease shown as *interrupted*."""
    return rx.match(
        document.index_status,
        (
            DocumentIndexStatus.DONE.value,
            rx.badge("indexed", color_scheme="green", variant="soft"),
        ),
        (
            DocumentIndexStatus.INDEXING.value,
            rx.badge(
                rx.spinner(size="1"),
                "indexing",
                color_scheme="blue",
                variant="soft",
            ),
        ),
        (
            DocumentIndexStatus.PENDING.value,
            rx.badge("pending", color_scheme="gray", variant="soft"),
        ),
        (
            DocumentIndexStatus.ERROR.value,
            rx.cond(
                document.error_message == INTERRUPTED_INDEXING_MESSAGE,
                # A run that died with its process. Not a failure of the document, and retryable —
                # which is why it is amber and named differently from a real error.
                rx.badge("interrupted", color_scheme="amber", variant="soft"),
                rx.badge("error", color_scheme="red", variant="soft"),
            ),
        ),
        rx.badge(document.index_status, variant="soft", color_scheme="gray"),
    )


def _error_tooltip(document: KnowledgeBaseDocumentDTO) -> rx.Component:
    """The reason an indexing run failed, on hover — the only part a user can act on."""
    return rx.cond(
        document.error_message,
        rx.tooltip(
            rx.icon("circle-alert", size=14, color="var(--amber-11)"),
            # Formatted rather than passed straight through: the DTO field is ``str | None`` and the
            # prop is ``str``, which Reflex warns about even inside the ``rx.cond`` that guards it.
            content=f"{document.error_message}",
        ),
    )


def _row_actions(document: KnowledgeBaseDocumentDTO) -> rx.Component:
    """Re-index, refresh and delete, for one document.

    The two indexing actions are disabled while a run owns the page: a second run on the same
    document would race on its lease, and a disabled button says so better than an error toast.
    """
    is_busy = KnowledgeBaseDetailState.busy_document_id == document.id
    return rx.hstack(
        rx.tooltip(
            rx.button(
                rx.icon("refresh-cw", size=14),
                variant="ghost",
                size="1",
                disabled=KnowledgeBaseDetailState.is_indexing,
                loading=is_busy,
                on_click=lambda: KnowledgeBaseDetailState.reindex_document(document.id),
            ),
            content="Re-index from the stored snapshot",
        ),
        rx.tooltip(
            rx.button(
                rx.icon("cloud-download", size=14),
                variant="ghost",
                size="1",
                disabled=KnowledgeBaseDetailState.is_indexing,
                loading=is_busy,
                on_click=lambda: KnowledgeBaseDetailState.refresh_document_from_source(document.id),
            ),
            content="Re-fetch from the source, then re-index",
        ),
        _delete_document_dialog(document),
        spacing="1",
        justify="end",
    )


def _delete_document_dialog(document: KnowledgeBaseDocumentDTO) -> rx.Component:
    """Delete, behind a confirmation. Destructive, so red and never one click away."""
    return rx.alert_dialog.root(
        rx.alert_dialog.trigger(
            rx.button(
                rx.icon("trash-2", size=14),
                variant="ghost",
                size="1",
                color_scheme="red",
            )
        ),
        rx.alert_dialog.content(
            rx.alert_dialog.title("Delete document"),
            rx.alert_dialog.description(
                f"'{document.filename}' will be removed from the knowledge base, together with its "
                "chunks and its stored copy. This cannot be undone.",
                margin_bottom="1rem",
            ),
            rx.flex(
                rx.alert_dialog.cancel(
                    rx.button("Cancel", variant="soft"),
                ),
                rx.alert_dialog.action(
                    rx.button(
                        "Delete",
                        color_scheme="red",
                        on_click=lambda: KnowledgeBaseDetailState.delete_document(document.id),
                    ),
                ),
                spacing="3",
                justify="end",
            ),
        ),
    )
