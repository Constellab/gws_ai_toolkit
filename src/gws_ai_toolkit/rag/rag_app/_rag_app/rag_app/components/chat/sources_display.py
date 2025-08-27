from typing import List

import reflex as rx
from gws_ai_toolkit.rag.common.rag_models import RagChunk


def source_item(source: RagChunk) -> rx.Component:
    """Display a single source item with click functionality."""
    return rx.link(
        rx.box(
            rx.hstack(
                rx.icon("file-text", size=16),
                rx.text(
                    source.document_name,
                    class_name="source-document-name"
                ),
                rx.spacer(),
                rx.hstack(
                    rx.text(
                        f"Score: {source.score:.2f}",
                    ),
                    rx.icon("external-link", size=12),
                    align="center",
                    spacing="1",
                ),
                align="center",
            ),
            padding="2",
        ),
        href=f"/ai-expert/{source.document_id}",
        text_decoration="none",
        cursor="pointer",
        style={":hover .source-document-name": {"text_decoration": "underline"}},
    )


def sources_display(sources: List[RagChunk]) -> rx.Component:
    """Component to display sources in an expandable section."""
    return rx.cond(
        sources,
        rx.accordion.root(
            rx.accordion.item(
                header="Sources",
                content=rx.accordion.content(
                    rx.vstack(
                        rx.foreach(sources, source_item),
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
