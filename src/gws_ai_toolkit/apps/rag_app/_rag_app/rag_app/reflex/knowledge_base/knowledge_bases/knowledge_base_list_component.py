"""The knowledge-base list page: every knowledge base, with create, open and delete.

The row itself opens the knowledge base, so the destructive action needs to be unmistakably separate:
delete is a red icon button behind an alert dialog that names the knowledge base and what disappears
with it. Nothing here deletes on one click.
"""

import reflex as rx
from gws_ai_toolkit.models.knowledge_base.knowledge_base_dto import KnowledgeBaseDTO

from ..core.form_field_component import form_field
from .knowledge_base_list_state import KNOWLEDGE_BASES_ROUTE, KnowledgeBaseListState


def knowledge_base_list_component() -> rx.Component:
    """The knowledge-base list page."""
    return rx.vstack(
        _header(),
        rx.cond(
            KnowledgeBaseListState.is_loading,
            rx.center(rx.spinner(size="3"), width="100%", padding="3rem"),
            rx.cond(
                KnowledgeBaseListState.has_knowledge_bases,
                _knowledge_base_table(),
                _empty_message(),
            ),
        ),
        _create_dialog(),
        spacing="4",
        padding="1em",
        width="100%",
    )


def _header() -> rx.Component:
    """Title and the create button."""
    return rx.vstack(
        rx.hstack(
            rx.heading("Knowledge bases", size="7"),
            rx.spacer(),
            rx.button(
                rx.icon("plus", size=16),
                "New knowledge base",
                on_click=KnowledgeBaseListState.open_create_dialog,
            ),
            align="center",
            width="100%",
        ),
        rx.text(
            "A knowledge base holds indexed documents that a chat can search.",
            size="2",
            color="var(--gray-11)",
        ),
        spacing="2",
        width="100%",
    )


def _knowledge_base_table() -> rx.Component:
    """The knowledge bases, newest chunking policy and all."""
    return rx.box(
        rx.table.root(
            rx.table.header(
                rx.table.row(
                    rx.table.column_header_cell("Name"),
                    rx.table.column_header_cell("Description"),
                    rx.table.column_header_cell("Instance scope"),
                    rx.table.column_header_cell("Chunking"),
                    rx.table.column_header_cell(""),
                )
            ),
            rx.table.body(
                rx.foreach(KnowledgeBaseListState.knowledge_bases, _knowledge_base_row),
            ),
            variant="surface",
            width="100%",
        ),
        width="100%",
        overflow_x="auto",
    )


def _knowledge_base_row(knowledge_base: KnowledgeBaseDTO) -> rx.Component:
    """One knowledge base: click it to open it, or delete it from the end of the row."""
    open_it = rx.redirect(f"{KNOWLEDGE_BASES_ROUTE}/{knowledge_base.id}")
    return rx.table.row(
        rx.table.cell(
            rx.text(knowledge_base.name, size="2", weight="medium"),
            on_click=open_it,
            cursor="pointer",
        ),
        rx.table.cell(
            rx.text(knowledge_base.description, size="2", color="var(--gray-11)"),
            on_click=open_it,
            cursor="pointer",
        ),
        rx.table.cell(rx.badge(knowledge_base.instance_scope, variant="soft", color_scheme="gray")),
        rx.table.cell(
            rx.text(
                f"{knowledge_base.chunk_size} / {knowledge_base.chunk_overlap}",
                size="2",
                color="var(--gray-11)",
            )
        ),
        rx.table.cell(
            rx.hstack(
                rx.button(
                    rx.icon("arrow-right", size=14),
                    "Open",
                    variant="soft",
                    size="1",
                    on_click=open_it,
                ),
                _delete_dialog(knowledge_base),
                spacing="2",
                justify="end",
            )
        ),
        align="center",
    )


def _delete_dialog(knowledge_base: KnowledgeBaseDTO) -> rx.Component:
    """Delete a knowledge base, behind a confirmation naming everything that goes with it."""
    return rx.alert_dialog.root(
        rx.alert_dialog.trigger(
            rx.button(
                rx.icon("trash-2", size=14),
                variant="ghost",
                size="1",
                color_scheme="red",
                loading=KnowledgeBaseListState.busy_knowledge_base_id == knowledge_base.id,
            )
        ),
        rx.alert_dialog.content(
            rx.alert_dialog.title("Delete knowledge base"),
            rx.alert_dialog.description(
                f"'{knowledge_base.name}' will be deleted, together with every document in it, "
                "their indexed chunks and their stored copies. This cannot be undone.",
                margin_bottom="1rem",
            ),
            rx.flex(
                rx.alert_dialog.cancel(rx.button("Cancel", variant="soft")),
                rx.alert_dialog.action(
                    rx.button(
                        "Delete",
                        color_scheme="red",
                        on_click=lambda: KnowledgeBaseListState.delete_knowledge_base(
                            knowledge_base.id
                        ),
                    ),
                ),
                spacing="3",
                justify="end",
            ),
        ),
    )


def _empty_message() -> rx.Component:
    """What the page says before the first knowledge base exists."""
    return rx.vstack(
        rx.icon("database", size=28, color="var(--gray-8)"),
        rx.text("No knowledge base yet.", size="2", weight="medium"),
        rx.text(
            "Create one, then add the documents it should index.",
            size="2",
            color="var(--gray-11)",
        ),
        rx.button(
            rx.icon("plus", size=16),
            "New knowledge base",
            on_click=KnowledgeBaseListState.open_create_dialog,
        ),
        align="center",
        justify="center",
        spacing="3",
        width="100%",
        padding="3rem 1rem",
    )


def _create_dialog() -> rx.Component:
    """The create form.

    The chunking policy is on the form because it cannot be changed freely afterwards: a new chunk
    size only affects documents indexed after the change. The instance scope is *not* on the form —
    it decides which vector space holds the chunks, and a typo would create a knowledge base in an
    instance nothing else addresses.
    """
    return rx.dialog.root(
        rx.dialog.content(
            rx.dialog.title("New knowledge base"),
            rx.vstack(
                form_field(
                    "Name",
                    rx.input(
                        placeholder="Sequencing protocols",
                        value=KnowledgeBaseListState.new_name,
                        on_change=KnowledgeBaseListState.set_new_name,
                        width="100%",
                    ),
                ),
                form_field(
                    "Description",
                    rx.text_area(
                        placeholder="What this knowledge base is for",
                        value=KnowledgeBaseListState.new_description,
                        on_change=KnowledgeBaseListState.set_new_description,
                        width="100%",
                        rows="2",
                    ),
                ),
                rx.hstack(
                    form_field(
                        "Chunk size",
                        rx.input(
                            value=KnowledgeBaseListState.new_chunk_size,
                            on_change=KnowledgeBaseListState.set_new_chunk_size,
                            type="number",
                            width="100%",
                        ),
                        hint="In tokens.",
                    ),
                    form_field(
                        "Chunk overlap",
                        rx.input(
                            value=KnowledgeBaseListState.new_chunk_overlap,
                            on_change=KnowledgeBaseListState.set_new_chunk_overlap,
                            type="number",
                            width="100%",
                        ),
                        hint="In tokens.",
                    ),
                    spacing="3",
                    width="100%",
                ),
                rx.hstack(
                    rx.spacer(),
                    rx.button(
                        "Cancel",
                        variant="soft",
                        on_click=KnowledgeBaseListState.close_create_dialog,
                    ),
                    rx.button(
                        rx.spinner(loading=KnowledgeBaseListState.is_creating),
                        "Create",
                        on_click=KnowledgeBaseListState.create_knowledge_base,
                        disabled=KnowledgeBaseListState.is_creating,
                    ),
                    spacing="3",
                    width="100%",
                ),
                spacing="4",
                width="100%",
            ),
            on_interact_outside=KnowledgeBaseListState.close_create_dialog,
            on_escape_key_down=KnowledgeBaseListState.close_create_dialog,
            max_width="30rem",
        ),
        open=KnowledgeBaseListState.create_dialog_open,
    )
