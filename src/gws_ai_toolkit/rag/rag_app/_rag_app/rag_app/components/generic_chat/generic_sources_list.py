from typing import List

import reflex as rx

from gws_ai_toolkit.rag.common.rag_models import RagChunk
from gws_ai_toolkit.rag.rag_app._rag_app.rag_app.components.generic_chat.chat_state_base import \
    ChatStateBase


def source_item(source: RagChunk, state: ChatStateBase) -> rx.Component:
    """Display a single source item with click functionality."""
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


def generic_sources_list(sources: List[RagChunk], state: ChatStateBase) -> rx.Component:
    """Component to display sources in an expandable section."""
    return rx.cond(
        sources,
        rx.accordion.root(
            rx.accordion.item(
                header="Sources",
                content=rx.accordion.content(
                    rx.vstack(
                        rx.foreach(sources, lambda source: source_item(source, state)),
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
