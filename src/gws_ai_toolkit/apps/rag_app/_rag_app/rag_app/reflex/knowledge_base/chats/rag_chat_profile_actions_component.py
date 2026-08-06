"""What can be done to one chat profile from anywhere, shared by the list row and the detail header.

*Chat* stays a visible button, because a profile exists to be talked to. Edit and delete live behind
one menu, so the same cluster fits a table cell and a page header, and so the row itself can be
clickable without several buttons fighting it for the click.

Publishing is deliberately **not** here. It is the one action whose consequences need to be read
before it is taken — it makes every bound knowledge base readable by anyone holding the token — so it
lives in the detail page's Publication section, next to the explanation of what it does, rather than
one click deep in a menu on a row. See ``_publication_section`` in
``rag_chat_profile_detail_component``.

Both callers reach ``RagChatProfileListState``, which owns the dialogs (see its module docstring).
The delete confirmation here is *controlled* rather than trigger-driven: the button that opens it is a
menu item, and a menu item cannot double as the trigger of another Radix primitive — same constraint
as ``knowledge_base_actions_menu``.
"""

import reflex as rx

from .rag_chat_profile_list_state import (
    ACTION_DIALOG_DELETE,
    RagChatProfileListState,
    is_action_dialog_open,
)
from .rag_chat_profile_row import ChatProfileRow


def rag_chat_profile_actions(profile: ChatProfileRow, icon_size: int = 14) -> rx.Component:
    """Chat, edit and delete for one chat profile. Publishing lives on the detail page.

    :param profile: the profile the actions act on
    :param icon_size: size of the menu trigger's icon, in pixels — smaller in a table row than in a
                      page header
    """
    return rx.hstack(
        rx.button(
            rx.icon("message-circle", size=14),
            "Chat",
            size="1",
            # Stops the list row's own click from also firing and navigating to the detail page.
            on_click=[rx.stop_propagation, RagChatProfileListState.start_chat(profile.id)],
        ),
        _actions_menu(profile, icon_size),
        _delete_dialog(profile),
        spacing="2",
        align="center",
        justify="end",
    )


def _actions_menu(profile: ChatProfileRow, icon_size: int) -> rx.Component:
    """Edit and delete, behind one menu button."""
    is_busy = RagChatProfileListState.busy_profile_id == profile.id
    return rx.menu.root(
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
                on_click=lambda: RagChatProfileListState.open_edit_dialog(profile.id),
            ),
            rx.menu.separator(),
            rx.menu.item(
                rx.icon("trash-2", size=14),
                "Delete",
                color_scheme="red",
                on_click=lambda: RagChatProfileListState.set_action_dialog_open(
                    True, ACTION_DIALOG_DELETE, profile.id
                ),
            ),
            on_click=lambda: rx.stop_propagation,  # Prevent the row's own click event
        ),
    )


def _delete_dialog(profile: ChatProfileRow) -> rx.Component:
    """Delete a profile, behind a confirmation saying what survives it."""
    return rx.alert_dialog.root(
        rx.alert_dialog.content(
            rx.alert_dialog.title("Delete chat profile"),
            rx.alert_dialog.description(
                f"'{profile.name}' will be deleted. Its knowledge bases and their documents are "
                "left untouched, and past conversations stay readable but can no longer be "
                "continued.",
                margin_bottom="1rem",
            ),
            rx.flex(
                rx.alert_dialog.cancel(rx.button("Cancel", variant="soft")),
                rx.alert_dialog.action(
                    rx.button(
                        "Delete",
                        color_scheme="red",
                        on_click=lambda: RagChatProfileListState.delete_profile(profile.id),
                    ),
                ),
                spacing="3",
                justify="end",
            ),
        ),
        open=is_action_dialog_open(profile.id, ACTION_DIALOG_DELETE),
        on_open_change=lambda is_open: RagChatProfileListState.set_action_dialog_open(
            is_open, ACTION_DIALOG_DELETE, profile.id
        ),
    )
