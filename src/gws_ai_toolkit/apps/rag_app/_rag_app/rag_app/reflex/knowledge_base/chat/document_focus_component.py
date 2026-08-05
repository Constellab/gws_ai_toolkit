"""Document Focus (issue #29): the in-chat "+" picker and the chips it fills.

Mirrors the AI Table chat's own attachment picker (``table_selection_menu()`` / ``_table_list()``):
a menu listing what can be added, and a row of removable chips for what already is. The menu only
ever offers documents already inside the conversation's chat profile — see
:meth:`KnowledgeBaseChatState._load_focusable_documents` — so focus can narrow that scope, never
widen it.
"""

import reflex as rx

from .knowledge_base_chat_state import DocumentFocusOption, KnowledgeBaseChatState


def _menu_item(document: DocumentFocusOption) -> rx.Component:
    return rx.menu.item(
        document.filename,
        on_click=KnowledgeBaseChatState.add_document_focus(document.id),
    )


def document_focus_menu() -> rx.Component:
    """Menu offering the profile's documents not already focused."""
    return rx.menu.root(
        rx.menu.trigger(
            rx.button(rx.icon("plus", size=16), variant="soft", size="1"),
        ),
        rx.menu.content(
            rx.foreach(KnowledgeBaseChatState.focus_options, _menu_item),
        ),
    )


def _document_chip(document: DocumentFocusOption) -> rx.Component:
    """One focused document, removable by clicking its "x"."""
    return rx.box(
        rx.hstack(
            rx.icon("file-text", size=14, color="var(--gray-10)"),
            rx.text(
                document.filename,
                font_size="12px",
                max_width="250px",
                overflow="hidden",
                text_overflow="ellipsis",
                white_space="nowrap",
            ),
            rx.tooltip(
                rx.icon(
                    "x",
                    size=16,
                    color="var(--gray-10)",
                    cursor="pointer",
                    on_click=KnowledgeBaseChatState.remove_document_focus(document),
                ),
                content="Remove from focus",
            ),
            spacing="1",
            align_items="center",
        ),
        padding_x="6px",
        padding_y="2px",
        border_radius="6px",
        background="var(--gray-3)",
        margin_right="6px",
        min_width="0",
        display="flex",
        align_items="center",
        user_select="none",
    )


def document_focus_composer(_state: type[rx.State]) -> rx.Component:
    """The row rendered above the composer: the current focus, then the "+" to add more.

    Signature matches ``ChatConfig.composer_extra``, but this component is knowledge-base specific
    and reads :class:`KnowledgeBaseChatState` directly rather than the state class handed to it.
    """
    return rx.hstack(
        rx.foreach(KnowledgeBaseChatState.focused_documents, _document_chip),
        document_focus_menu(),
        spacing="1",
        align_items="center",
        margin_bottom="8px",
        width="100%",
        wrap="wrap",
    )
