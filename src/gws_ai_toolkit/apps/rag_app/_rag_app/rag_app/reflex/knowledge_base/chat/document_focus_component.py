"""Document Focus (issue #29): the in-chat "+" picker and the chips it fills.

Mirrors the AI Table chat's own attachment picker (``table_selection_menu()`` / ``_table_list()``):
a menu listing what can be added, and a row of removable chips for what already is. The menu only
ever offers documents already inside the conversation's chat profile — see
:meth:`KnowledgeBaseChatState._load_focusable_documents` — so focus can narrow that scope, never
widen it.

Also holds the read-only counterpart (issue #31): each historical user message carries its own
``focused_document_ids``, rendered as non-removable chips underneath it — mirroring
``_table_chip`` / ``ChatUserMessageTableFront.tables`` in the AI Table chat.
"""

import reflex as rx
from gws_ai_toolkit.models.chat.message.chat_user_message import ChatUserMessageText

from ...chat_base.messages_list_component import user_message_base
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


def _focus_chip(document_id: str) -> rx.Component:
    """One document a historical message was focused on — read-only, no "x"."""
    filename = KnowledgeBaseChatState.document_filenames_by_id.get(document_id, document_id)
    return rx.box(
        rx.hstack(
            rx.icon("file-text", size=14, color="var(--gray-10)"),
            rx.text(
                filename,
                font_size="11px",
                max_width="200px",
                overflow="hidden",
                text_overflow="ellipsis",
                white_space="nowrap",
            ),
            spacing="1",
            align_items="center",
        ),
        padding_x="6px",
        padding_y="2px",
        border_radius="4px",
        background="var(--gray-3)",
        margin_right="4px",
        margin_top="4px",
        min_width="0",
        display="inline-flex",
        align_items="center",
        user_select="none",
    )


def user_message_with_focus_chips(message: ChatUserMessageText) -> rx.Component:
    """A user message, with the documents focused when it was sent shown underneath it.

    Mirrors ``_user_dataframe_text_message_content`` in the AI Table chat: the bubble first, then the
    chip row, only when there is focus to show.
    """
    return rx.vstack(
        user_message_base(message),
        rx.cond(
            message.focused_document_ids,
            rx.hstack(
                rx.foreach(message.focused_document_ids, _focus_chip),
                width="100%",
                wrap="wrap",
                justify="end",
            ),
        ),
        spacing="0",
        width="100%",
        align_items="flex-start",
    )
