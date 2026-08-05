"""Edit and delete, behind one menu button, for one knowledge base.

Shared by the list table and the detail page header, so the two do not drift: both call
``KnowledgeBaseListState`` directly, which is what actually owns the edit dialog and the delete
confirmation (see its module docstring for how it also keeps the detail page in sync).

Delete stays behind a confirmation, but a controlled one rather than a Radix alert-dialog trigger: the
button that opens it is a menu item, and a menu item cannot double as a trigger for another Radix
primitive (mirrors ``_delete_document_dialog`` in ``document_table_component.py``).
"""

import reflex as rx
from gws_ai_toolkit.models.knowledge_base.knowledge_base_dto import KnowledgeBaseDTO

from .knowledge_base_list_state import KnowledgeBaseListState


def knowledge_base_actions_menu(knowledge_base: KnowledgeBaseDTO, icon_size: int = 14) -> rx.Component:
    """Edit and delete for one knowledge base, behind one menu button.

    :param knowledge_base: the knowledge base the menu acts on
    :param icon_size: size of the trigger's icon, in pixels — smaller in a table row than in a page
                      header
    """
    is_busy = KnowledgeBaseListState.busy_knowledge_base_id == knowledge_base.id
    return rx.hstack(
        rx.menu.root(
            rx.menu.trigger(
                rx.button(
                    rx.cond(
                        is_busy, rx.spinner(size="1"), rx.icon("ellipsis-vertical", size=icon_size)
                    ),
                    variant="ghost",
                    size="1",
                )
            ),
            rx.menu.content(
                rx.menu.item(
                    rx.icon("pencil", size=14),
                    "Edit",
                    on_click=lambda: KnowledgeBaseListState.open_edit_dialog(knowledge_base.id),
                ),
                rx.menu.separator(),
                rx.menu.item(
                    rx.icon("trash-2", size=14),
                    "Delete",
                    color_scheme="red",
                    on_click=lambda: KnowledgeBaseListState.set_delete_dialog_open(
                        True, knowledge_base.id
                    ),
                ),
                on_click=lambda: rx.stop_propagation,  # Prevent row click event
            ),
        ),
        _delete_dialog(knowledge_base),
        justify="end",
    )


def _delete_dialog(knowledge_base: KnowledgeBaseDTO) -> rx.Component:
    """Delete a knowledge base, behind a confirmation naming everything that goes with it."""
    return rx.alert_dialog.root(
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
        open=KnowledgeBaseListState.delete_dialog_knowledge_base_id == knowledge_base.id,
        on_open_change=lambda is_open: KnowledgeBaseListState.set_delete_dialog_open(
            is_open, knowledge_base.id
        ),
    )
