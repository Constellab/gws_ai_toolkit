import reflex as rx
from gws_ai_toolkit.rag.common.rag_models import RagChunk

from .document_chunks_state import DocumentChunksState


def _chunk_item(chunk: RagChunk, index: int) -> rx.Component:
    """Render a single chunk item."""
    return rx.box(
        rx.vstack(
            rx.text(f"Chunk {index} ({chunk.id})", size="1", color="gray"),
            rx.box(
                rx.cond(
                    chunk.content,
                    rx.cond(
                        DocumentChunksState.view_as_raw,
                        rx.text(chunk.content, white_space="pre-wrap"),
                        rx.markdown(chunk.content, class_name="dense-markdown"),
                    ),
                    rx.text("No content"),
                ),
                white_space="pre-wrap",
                max_height="300px",
                overflow="auto",
            ),
            spacing="2",
            align="start",
        ),
        padding="12px",
        border="1px solid var(--gray-6)",
        border_radius="6px",
        width="100%",
    )


def document_chunks_dialog():
    """Dialog component to display RAG document chunks."""
    return rx.dialog.root(
        rx.dialog.content(
            rx.hstack(
                rx.dialog.title("RAG Document Chunks"),
                rx.spacer(),
                rx.button(
                    rx.cond(DocumentChunksState.view_as_raw, "View as Markdown", "View as Raw"),
                    on_click=DocumentChunksState.toggle_raw_view,
                    variant="outline",
                    size="2",
                ),
            ),
            rx.dialog.description("Showing chunks for the selected document"),
            rx.cond(
                DocumentChunksState.chunks_loading & (DocumentChunksState.chunks_page == 1),
                rx.center(rx.spinner(size="3"), height="200px"),
                rx.scroll_area(
                    rx.vstack(
                        rx.cond(
                            DocumentChunksState.chunks,
                            rx.foreach(DocumentChunksState.chunks, _chunk_item),
                            rx.text("No chunks found", color="gray"),
                        ),
                        spacing="3",
                        width="100%",
                    ),
                    flex="1",
                    width="100%",
                ),
            ),
            rx.hstack(
                rx.button(
                    rx.spinner(loading=DocumentChunksState.chunks_loading),
                    "Load More",
                    on_click=DocumentChunksState.load_next_chunks_page,
                    disabled=DocumentChunksState.chunks_loading,
                    variant="outline",
                ),
                rx.button(
                    "Close", on_click=DocumentChunksState.close_chunks_dialog, variant="solid"
                ),
                justify="between",
                width="100%",
                margin_top="16px",
            ),
            max_width="800px",
            width="90vw",
            height="90vh",
            display="flex",
            flex_direction="column",
        ),
        open=DocumentChunksState.chunks_dialog_open,
        on_open_change=DocumentChunksState.set_chunks_dialog_open,
    )


def load_chunks_button(dataset_id: str, document_id: str):
    """Button to load and display document chunks."""
    return rx.button(
        "Load Chunks",
        on_click=lambda: [
            DocumentChunksState.open_chunks_dialog(dataset_id, document_id),
            DocumentChunksState.load_chunks(),
        ],
        variant="outline",
    )
