"""The knowledge-base list page: every knowledge base, with create, edit, open and delete.

The row itself opens the knowledge base; edit and delete live behind ``knowledge_base_actions_menu``,
shared with the detail page's header so the two do not drift.
"""

import reflex as rx
from gws_ai_toolkit.models.knowledge_base.knowledge_base_dto import KnowledgeBaseDTO

from ..core.form_field_component import form_field
from .knowledge_base_actions_menu_component import knowledge_base_actions_menu
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
        knowledge_base_edit_dialog(),
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
    """One knowledge base: click anywhere on the row to open it, or delete it from the end of the row."""
    return rx.table.row(
        rx.table.cell(rx.text(knowledge_base.name, size="2", weight="medium")),
        rx.table.cell(rx.text(knowledge_base.description, size="2", color="var(--gray-11)")),
        rx.table.cell(rx.badge(knowledge_base.instance_scope, variant="soft", color_scheme="gray")),
        rx.table.cell(
            rx.text(
                f"{knowledge_base.chunk_size} / {knowledge_base.chunk_overlap}",
                size="2",
                color="var(--gray-11)",
            )
        ),
        rx.table.cell(knowledge_base_actions_menu(knowledge_base, icon_size=14)),
        align="center",
        style={":hover": {"background_color": "var(--gray-3)"}, "cursor": "pointer"},
        on_click=lambda: rx.redirect(f"{KNOWLEDGE_BASES_ROUTE}/{knowledge_base.id}"),
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


def knowledge_base_edit_dialog() -> rx.Component:
    """The create-and-edit form.

    Rendered on both the list page and the detail page: ``KnowledgeBaseListState.open_edit_dialog`` is
    reachable from either, via ``knowledge_base_actions_menu``, so the dialog itself has to be present
    wherever that menu is.

    The chunking policy is only shown while creating: it cannot be changed freely afterwards, since a
    new chunk size only affects documents indexed after the change. The instance scope is never on the
    form at all — it decides which vector space holds the chunks, and a typo would create a knowledge
    base in an instance nothing else addresses.
    """
    return rx.dialog.root(
        rx.dialog.content(
            rx.dialog.title(KnowledgeBaseListState.dialog_title),
            rx.vstack(
                form_field(
                    "Name",
                    rx.input(
                        placeholder="Sequencing protocols",
                        value=KnowledgeBaseListState.form_name,
                        on_change=KnowledgeBaseListState.set_form_name,
                        width="100%",
                    ),
                ),
                form_field(
                    "Description",
                    rx.text_area(
                        placeholder="What this knowledge base is for",
                        value=KnowledgeBaseListState.form_description,
                        on_change=KnowledgeBaseListState.set_form_description,
                        width="100%",
                        rows="2",
                    ),
                ),
                rx.cond(
                    KnowledgeBaseListState.is_editing_knowledge_base,
                    rx.fragment(),
                    rx.hstack(
                        form_field(
                            "Chunk size",
                            rx.input(
                                value=KnowledgeBaseListState.form_chunk_size,
                                on_change=KnowledgeBaseListState.set_form_chunk_size,
                                type="number",
                                width="100%",
                            ),
                            hint="In tokens.",
                        ),
                        form_field(
                            "Chunk overlap",
                            rx.input(
                                value=KnowledgeBaseListState.form_chunk_overlap,
                                on_change=KnowledgeBaseListState.set_form_chunk_overlap,
                                type="number",
                                width="100%",
                            ),
                            hint="In tokens.",
                        ),
                        spacing="3",
                        width="100%",
                    ),
                ),
                rx.hstack(
                    rx.spacer(),
                    rx.button(
                        "Cancel",
                        variant="soft",
                        on_click=KnowledgeBaseListState.close_dialog,
                    ),
                    rx.button(
                        rx.spinner(loading=KnowledgeBaseListState.is_saving),
                        "Save",
                        on_click=KnowledgeBaseListState.save_knowledge_base,
                        disabled=KnowledgeBaseListState.is_saving,
                    ),
                    spacing="3",
                    width="100%",
                ),
                spacing="4",
                width="100%",
            ),
            on_interact_outside=KnowledgeBaseListState.close_dialog,
            on_escape_key_down=KnowledgeBaseListState.close_dialog,
            max_width="30rem",
        ),
        open=KnowledgeBaseListState.dialog_open,
    )
