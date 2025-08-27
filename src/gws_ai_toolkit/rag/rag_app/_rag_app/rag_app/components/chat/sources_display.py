from typing import List

import reflex as rx
from gws_ai_toolkit.rag.common.rag_models import RagChunk


def source_item(source: RagChunk) -> rx.Component:
    """Display a single source item with click functionality."""
    return rx.link(
        rx.box(
            rx.hstack(
                rx.icon("file-text", size=16, color="blue.500"),
                rx.text(
                    source.document_name,
                    font_weight="medium",
                    font_size="sm",
                ),
                rx.spacer(),
                rx.hstack(
                    rx.text(
                        f"Score: {source.score:.2f}",
                        font_size="xs",
                        color="gray.600",
                    ),
                    rx.icon("external-link", size=12, color="blue.500"),
                    align="center",
                    spacing="1",
                ),
                align="center",
            ),
            padding="2",
            border_radius="md",
            _hover={"background_color": "gray.50", "cursor": "pointer"},
            transition="background-color 0.2s ease",
        ),
        href=f"/ai-expert/{source.document_id}",
        text_decoration="none",
        _hover={"text_decoration": "none"},
    )


def sources_display(sources: List[RagChunk]) -> rx.Component:
    """Component to display sources in an expandable section."""
    return rx.cond(
        sources,
        rx.accordion.root(
            rx.accordion.item(
                header=rx.accordion.trigger(
                    rx.text("Sources", font_size="sm", font_weight="medium"),
                ),
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
            variant="outline"
        ),
    )
