"""The chat-profile page: every profile, with the actions that make one usable.

The row's primary action is *Chat*, because a profile exists to be talked to. Edit is next to it, and
delete is a red icon button behind an alert dialog — the row itself does nothing destructive on one
click.

The table says two things a name and a model cannot: a profile bound to no knowledge base retrieves
nothing, and a profile bound to a knowledge base that has since been deleted searches less than its
author configured. Both are shown, because neither is visible from the answer the chat gives.
"""

import reflex as rx
from gws_ai_toolkit.models.knowledge_base.knowledge_base_dto import KnowledgeBaseDTO

from ..core.form_field_component import form_field
from .rag_chat_profile_list_state import ChatProfileRow, RagChatProfileListState


def rag_chat_profile_list_component() -> rx.Component:
    """The chat-profile page."""
    return rx.vstack(
        _header(),
        rx.cond(
            RagChatProfileListState.is_loading,
            rx.center(rx.spinner(size="3"), width="100%", padding="3rem"),
            rx.cond(
                RagChatProfileListState.has_profiles,
                _profile_table(),
                _empty_message(),
            ),
        ),
        _edit_dialog(),
        _token_dialog(),
        spacing="4",
        padding="1em",
        width="100%",
    )


def _header() -> rx.Component:
    """Title and the create button."""
    return rx.vstack(
        rx.hstack(
            rx.heading("Chat profiles", size="7"),
            rx.spacer(),
            rx.button(
                rx.icon("plus", size=16),
                "New chat profile",
                on_click=RagChatProfileListState.open_create_dialog,
            ),
            align="center",
            width="100%",
        ),
        rx.text(
            "A chat profile decides how a chat answers: its prompt, its model, and which knowledge "
            "bases it searches.",
            size="2",
            color="var(--gray-11)",
        ),
        spacing="2",
        width="100%",
    )


def _profile_table() -> rx.Component:
    """The profiles, with what each one searches and how."""
    return rx.box(
        rx.table.root(
            rx.table.header(
                rx.table.row(
                    rx.table.column_header_cell("Name"),
                    rx.table.column_header_cell("Model"),
                    rx.table.column_header_cell("Knowledge bases"),
                    rx.table.column_header_cell("Passages"),
                    rx.table.column_header_cell("Threshold"),
                    rx.table.column_header_cell("Status"),
                    rx.table.column_header_cell(""),
                )
            ),
            rx.table.body(
                rx.foreach(RagChatProfileListState.profile_rows, _profile_row),
            ),
            variant="surface",
            width="100%",
        ),
        width="100%",
        overflow_x="auto",
    )


def _profile_row(profile: ChatProfileRow) -> rx.Component:
    """One profile: chat with it, edit it, or delete it."""
    return rx.table.row(
        rx.table.cell(rx.text(profile.name, size="2", weight="medium")),
        rx.table.cell(rx.code(profile.model, size="1")),
        rx.table.cell(_knowledge_bases_cell(profile)),
        rx.table.cell(rx.text(profile.top_k_label, size="2", color="var(--gray-11)")),
        rx.table.cell(rx.text(profile.threshold_label, size="2", color="var(--gray-11)")),
        rx.table.cell(_status_cell(profile)),
        rx.table.cell(
            rx.hstack(
                rx.button(
                    rx.icon("message-circle", size=14),
                    "Chat",
                    size="1",
                    on_click=lambda: RagChatProfileListState.start_chat(profile.id),
                ),
                rx.button(
                    rx.icon("pencil", size=14),
                    "Edit",
                    variant="soft",
                    size="1",
                    on_click=lambda: RagChatProfileListState.open_edit_dialog(profile.id),
                ),
                _publish_actions(profile),
                _delete_dialog(profile),
                spacing="2",
                justify="end",
            )
        ),
        align="center",
    )


def _status_cell(profile: ChatProfileRow) -> rx.Component:
    """Whether this profile is published, and since when — the token itself never appears here."""
    return rx.vstack(
        rx.cond(
            profile.is_published,
            rx.badge("Published", color_scheme="green", variant="soft", size="1"),
            rx.badge("Not published", color_scheme="gray", variant="soft", size="1"),
        ),
        rx.cond(
            profile.is_published,
            rx.text(profile.published_label, size="1", color="var(--gray-10)"),
        ),
        spacing="1",
        align="start",
    )


def _knowledge_bases_cell(profile: ChatProfileRow) -> rx.Component:
    """What this profile searches — and what it says when the answer is "nothing"."""
    return rx.vstack(
        rx.cond(
            profile.is_unbound,
            rx.hstack(
                rx.icon("triangle-alert", size=14, color="var(--gray-9)"),
                rx.text("Binds nothing, so it retrieves nothing", size="1", color="var(--gray-11)"),
                align="center",
                spacing="1",
            ),
            rx.flex(
                rx.foreach(
                    profile.knowledge_base_names,
                    lambda name: rx.badge(name, variant="soft", color_scheme="gray", size="1"),
                ),
                wrap="wrap",
                gap="4px",
            ),
        ),
        rx.cond(
            profile.has_dangling_bindings,
            rx.text(
                "Some bound knowledge bases were deleted and are no longer searched.",
                size="1",
                color="var(--gray-10)",
            ),
        ),
        spacing="1",
        align="start",
    )


def _publish_actions(profile: ChatProfileRow) -> rx.Component:
    """Publish, rotate the token, or un-publish — admin-only, since publishing exposes documents.

    The button shown only decides which confirmation opens; the service enforces the admin
    restriction on its own, so hiding it here is a UX courtesy, not the security boundary.
    """
    return rx.cond(
        RagChatProfileListState.is_admin,
        rx.cond(
            profile.is_published,
            rx.hstack(
                _publish_dialog(profile, rotate=True),
                _unpublish_dialog(profile),
                spacing="2",
            ),
            _publish_dialog(profile, rotate=False),
        ),
    )


def _publish_dialog(profile: ChatProfileRow, *, rotate: bool) -> rx.Component:
    """Confirm publishing a profile, or rotating an already-published one's token.

    Publishing is the moment the world-readable warning has to land, because it is the moment it
    becomes true: V1 has no per-document access control, so every knowledge base this profile
    searches becomes readable by anyone who holds the token minted here.
    """
    label = "Rotate token" if rotate else "Publish"
    icon = "refresh-cw" if rotate else "globe"
    description = (
        f"'{profile.name}' is already published. Rotating mints a new token immediately — the "
        "current one stops working the moment you confirm."
        if rotate
        else (
            f"Publishing '{profile.name}' makes every knowledge base it searches readable by "
            "anyone who holds its token — this version has no per-document access control. The "
            "token is shown once, right after you confirm: copy it immediately, and never paste "
            "it anywhere the documents themselves should not be readable."
        )
    )
    return rx.alert_dialog.root(
        rx.alert_dialog.trigger(
            rx.button(
                rx.icon(icon, size=14),
                label,
                variant="soft" if rotate else "solid",
                size="1",
                loading=RagChatProfileListState.busy_profile_id == profile.id,
            )
        ),
        rx.alert_dialog.content(
            rx.alert_dialog.title(label),
            rx.alert_dialog.description(description, margin_bottom="1rem"),
            rx.flex(
                rx.alert_dialog.cancel(rx.button("Cancel", variant="soft")),
                rx.alert_dialog.action(
                    rx.button(
                        label,
                        on_click=lambda: RagChatProfileListState.publish_profile(profile.id),
                    ),
                ),
                spacing="3",
                justify="end",
            ),
        ),
    )


def _unpublish_dialog(profile: ChatProfileRow) -> rx.Component:
    """Confirm un-publishing — revokes access for anyone holding the current token immediately."""
    return rx.alert_dialog.root(
        rx.alert_dialog.trigger(
            rx.button(
                rx.icon("globe-lock", size=14),
                "Un-publish",
                variant="soft",
                color_scheme="red",
                size="1",
                loading=RagChatProfileListState.busy_profile_id == profile.id,
            )
        ),
        rx.alert_dialog.content(
            rx.alert_dialog.title("Un-publish chat profile"),
            rx.alert_dialog.description(
                f"Anyone holding '{profile.name}''s current token loses access immediately. The "
                "profile itself is kept, and can be published again later with a new token.",
                margin_bottom="1rem",
            ),
            rx.flex(
                rx.alert_dialog.cancel(rx.button("Cancel", variant="soft")),
                rx.alert_dialog.action(
                    rx.button(
                        "Un-publish",
                        color_scheme="red",
                        on_click=lambda: RagChatProfileListState.unpublish_profile(profile.id),
                    ),
                ),
                spacing="3",
                justify="end",
            ),
        ),
    )


def _token_dialog() -> rx.Component:
    """The token just minted by a publish or a rotation, shown exactly once.

    Closing this dialog does not revoke anything — the profile stays published — it only stops the
    token from being displayed again, which is why "Done" is its only way out.
    """
    return rx.dialog.root(
        rx.dialog.content(
            rx.dialog.title(f"'{RagChatProfileListState.minted_token_profile_name}' is published"),
            rx.vstack(
                rx.text(
                    "Anyone who holds this token can read everything this profile's bound "
                    "knowledge bases contain — there is no per-document access control in this "
                    "version. Copy it now: it will not be shown again.",
                    size="2",
                    color="var(--gray-11)",
                ),
                rx.code_block(RagChatProfileListState.minted_token, can_copy=True, width="100%"),
                spacing="3",
                width="100%",
            ),
            rx.hstack(
                rx.spacer(),
                rx.button("Done", on_click=RagChatProfileListState.close_token_dialog),
                width="100%",
                margin_top="1rem",
            ),
            on_interact_outside=RagChatProfileListState.close_token_dialog,
            on_escape_key_down=RagChatProfileListState.close_token_dialog,
            max_width="32rem",
        ),
        open=RagChatProfileListState.token_dialog_open,
    )


def _delete_dialog(profile: ChatProfileRow) -> rx.Component:
    """Delete a profile, behind a confirmation saying what survives it."""
    return rx.alert_dialog.root(
        rx.alert_dialog.trigger(
            rx.button(
                rx.icon("trash-2", size=14),
                variant="ghost",
                size="1",
                color_scheme="red",
                loading=RagChatProfileListState.busy_profile_id == profile.id,
            )
        ),
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
    )


def _empty_message() -> rx.Component:
    """What the page says before the first profile exists."""
    return rx.vstack(
        rx.icon("message-circle", size=28, color="var(--gray-8)"),
        rx.text("No chat profile yet.", size="2", weight="medium"),
        rx.text(
            "Create one, bind it to the knowledge bases it should search, then start chatting.",
            size="2",
            color="var(--gray-11)",
        ),
        rx.button(
            rx.icon("plus", size=16),
            "New chat profile",
            on_click=RagChatProfileListState.open_create_dialog,
        ),
        align="center",
        justify="center",
        spacing="3",
        width="100%",
        padding="3rem 1rem",
    )


def _edit_dialog() -> rx.Component:
    """The create / edit form — one dialog, so the two cannot drift apart."""
    return rx.dialog.root(
        rx.dialog.content(
            rx.dialog.title(RagChatProfileListState.dialog_title),
            rx.vstack(
                form_field(
                    "Name",
                    rx.input(
                        placeholder="Support assistant",
                        value=RagChatProfileListState.form_name,
                        on_change=RagChatProfileListState.set_form_name,
                        width="100%",
                    ),
                ),
                form_field(
                    "System prompt",
                    rx.text_area(
                        value=RagChatProfileListState.form_system_prompt,
                        on_change=RagChatProfileListState.set_form_system_prompt,
                        width="100%",
                        rows="8",
                    ),
                    hint="What the model is told before every question, including when to search.",
                ),
                form_field(
                    "Model",
                    rx.input(
                        placeholder="openai:gpt-4.1-mini",
                        value=RagChatProfileListState.form_model,
                        on_change=RagChatProfileListState.set_form_model,
                        width="100%",
                    ),
                    hint="A 'provider:model' string.",
                ),
                rx.hstack(
                    form_field(
                        "Passages per search",
                        rx.input(
                            value=RagChatProfileListState.form_top_k,
                            on_change=RagChatProfileListState.set_form_top_k,
                            type="number",
                            width="100%",
                        ),
                        hint="How many passages one search returns.",
                    ),
                    form_field(
                        "Score threshold",
                        rx.input(
                            placeholder="No threshold",
                            value=RagChatProfileListState.form_score_threshold,
                            on_change=RagChatProfileListState.set_form_score_threshold,
                            type="number",
                            step="0.001",
                            width="100%",
                        ),
                        hint="Leave empty to keep every passage retrieved.",
                    ),
                    spacing="3",
                    width="100%",
                ),
                _knowledge_base_picker(),
                rx.hstack(
                    rx.spacer(),
                    rx.button(
                        "Cancel",
                        variant="soft",
                        on_click=RagChatProfileListState.close_dialog,
                    ),
                    rx.button(
                        rx.spinner(loading=RagChatProfileListState.is_saving),
                        "Save",
                        on_click=RagChatProfileListState.save_profile,
                        disabled=RagChatProfileListState.is_saving,
                    ),
                    spacing="3",
                    width="100%",
                ),
                spacing="4",
                width="100%",
            ),
            on_interact_outside=RagChatProfileListState.close_dialog,
            on_escape_key_down=RagChatProfileListState.close_dialog,
            max_width="36rem",
        ),
        open=RagChatProfileListState.dialog_open,
    )


def _knowledge_base_picker() -> rx.Component:
    """The bound knowledge bases: a checkbox each, because an id must not be typed."""
    return form_field(
        "Knowledge bases",
        rx.cond(
            RagChatProfileListState.has_knowledge_bases,
            rx.vstack(
                rx.foreach(RagChatProfileListState.knowledge_bases, _knowledge_base_checkbox),
                spacing="2",
                width="100%",
                max_height="12rem",
                overflow_y="auto",
                padding="0.5rem",
                border="1px solid var(--gray-5)",
                border_radius="var(--radius-2)",
            ),
            rx.text(
                "No knowledge base exists yet. Create one first, or this profile will retrieve "
                "nothing.",
                size="2",
                color="var(--gray-11)",
            ),
        ),
        hint="A search is scoped to the knowledge bases ticked here.",
    )


def _knowledge_base_checkbox(knowledge_base: KnowledgeBaseDTO) -> rx.Component:
    """One knowledge base the profile may bind."""
    return rx.checkbox(
        knowledge_base.name,
        checked=RagChatProfileListState.form_knowledge_base_ids.contains(knowledge_base.id),
        on_change=lambda checked: RagChatProfileListState.toggle_knowledge_base(
            knowledge_base.id, checked
        ),
        size="2",
    )
