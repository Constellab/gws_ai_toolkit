"""The detail page of one chat profile: everything it is configured with, one section at a time.

The page exists for what a table row cannot hold. Two things in particular: the system prompt, which
is a paragraph and is the single biggest determinant of how the chat answers, and the publication
warning, which a row can only fit inside a confirmation dialog and which is worth reading *before*
deciding to publish rather than in the second it takes to click through.

The header's actions are the row's actions, not a second set: ``rag_chat_profile_actions`` is the
same component the list table renders, and ``RagChatProfileListState`` owns the edit dialog it opens,
so that dialog has to be rendered on this page too for it to be able to show.

Publishing is the exception, and lives only here — see :func:`_publication_section`. Its two
confirmations and the token dialog are therefore this page's, not the shared cluster's, even though
the handlers behind them still sit on ``RagChatProfileListState`` with every other mutation.
"""

import reflex as rx
from gws_ai_toolkit.models.knowledge_base.knowledge_base_dto import KnowledgeBaseDTO

from ..core.summary_item_component import summary_item
from ..knowledge_bases.knowledge_base_list_state import KNOWLEDGE_BASES_ROUTE
from .rag_chat_profile_actions_component import rag_chat_profile_actions
from .rag_chat_profile_detail_state import RagChatProfileDetailState
from .rag_chat_profile_list_component import rag_chat_profile_edit_dialog
from .rag_chat_profile_list_state import (
    ACTION_DIALOG_PUBLISH,
    ACTION_DIALOG_UNPUBLISH,
    CHAT_PROFILES_ROUTE,
    RagChatProfileListState,
    is_action_dialog_open,
)


def rag_chat_profile_detail_component() -> rx.Component:
    """The chat-profile detail page."""
    return rx.vstack(
        _breadcrumb(),
        rx.cond(
            RagChatProfileDetailState.profile,
            rx.vstack(
                _header(),
                _summary(),
                rx.divider(),
                _knowledge_bases_section(),
                rx.divider(),
                _retrieval_section(),
                rx.divider(),
                _system_prompt_section(),
                rx.divider(),
                _publication_section(),
                spacing="4",
                width="100%",
            ),
            _not_found_message(),
        ),
        rag_chat_profile_edit_dialog(),
        spacing="4",
        padding="1em",
        width="100%",
    )


def _breadcrumb() -> rx.Component:
    """The way back to the list."""
    return rx.button(
        rx.icon("arrow-left", size=16),
        "Chat profiles",
        variant="ghost",
        size="2",
        on_click=rx.redirect(CHAT_PROFILES_ROUTE),
    )


def _header() -> rx.Component:
    """Name, publication badge, and the actions the list row also carries."""
    return rx.hstack(
        rx.heading(RagChatProfileDetailState.profile.name, size="7"),
        rx.cond(
            RagChatProfileDetailState.profile.is_published,
            rx.badge("Published", color_scheme="green", variant="soft", size="2"),
            rx.badge("Not published", color_scheme="gray", variant="soft", size="2"),
        ),
        rx.spacer(),
        rag_chat_profile_actions(RagChatProfileDetailState.profile_row, icon_size=22),
        align="center",
        width="100%",
    )


def _summary() -> rx.Component:
    """The four facts that decide what an answer is made of."""
    return rx.hstack(
        summary_item("cpu", RagChatProfileDetailState.profile.model, "model"),
        summary_item(
            "list-ordered",
            RagChatProfileDetailState.profile.top_k.to_string(),
            "passages per search",
        ),
        summary_item(
            "gauge", RagChatProfileDetailState.profile_row.threshold_label, "score threshold"
        ),
        summary_item(
            "database",
            RagChatProfileDetailState.bound_knowledge_bases.length().to_string(),
            "knowledge bases",
        ),
        spacing="5",
        wrap="wrap",
        width="100%",
    )


def _section(title: str, hint: str, *content: rx.Component) -> rx.Component:
    """One section of the page: a heading, a line saying what it decides, then the content.

    :param title: the section's heading
    :param hint: what this part of the configuration changes about an answer
    :param content: the section's body
    """
    return rx.vstack(
        rx.heading(title, size="5"),
        rx.text(hint, size="2", color="var(--gray-11)"),
        *content,
        spacing="3",
        width="100%",
        align="start",
    )


def _knowledge_bases_section() -> rx.Component:
    """What this profile searches, as links to the knowledge bases themselves."""
    return _section(
        "Knowledge bases",
        "A search is scoped to these. Anything outside them is not retrievable from this profile.",
        rx.cond(
            RagChatProfileDetailState.bound_knowledge_bases,
            rx.flex(
                rx.foreach(RagChatProfileDetailState.bound_knowledge_bases, _knowledge_base_link),
                wrap="wrap",
                gap="0.5rem",
            ),
            rx.hstack(
                rx.icon("triangle-alert", size=16, color="var(--gray-9)"),
                rx.text(
                    "This profile binds nothing, so it retrieves nothing. Edit it to bind the "
                    "knowledge bases it should search.",
                    size="2",
                    color="var(--gray-11)",
                ),
                align="center",
                spacing="2",
            ),
        ),
        rx.cond(
            RagChatProfileDetailState.dangling_binding_count > 0,
            # The text goes in directly: ``rx.callout`` already wraps its content in a paragraph, and
            # an ``rx.text`` inside it nests one <p> in another, which React refuses to hydrate.
            rx.callout(
                f"{RagChatProfileDetailState.dangling_binding_count} bound knowledge base(s) "
                "no longer exist and are silently skipped at search time. Editing this profile "
                "and saving it drops them.",
                size="2",
                icon="triangle-alert",
                color_scheme="gray",
                width="100%",
            ),
        ),
    )


def _knowledge_base_link(knowledge_base: KnowledgeBaseDTO) -> rx.Component:
    """One bound knowledge base, as a link to its own page."""
    return rx.link(
        rx.badge(
            rx.icon("database", size=12),
            knowledge_base.name,
            variant="soft",
            color_scheme="gray",
            size="2",
        ),
        href=f"{KNOWLEDGE_BASES_ROUTE}/{knowledge_base.id}",
    )


def _retrieval_section() -> rx.Component:
    """How much a search brings back, and what it throws away."""
    return _section(
        "Retrieval",
        "What one call to the search tool returns before the model ever sees it.",
        rx.hstack(
            _retrieval_item(
                "Passages per search",
                RagChatProfileDetailState.profile.top_k.to_string(),
                "The most passages one search can return. Raising it gives the model more to work "
                "from, and more to be distracted by.",
            ),
            _retrieval_item(
                "Score threshold",
                RagChatProfileDetailState.profile_row.threshold_label,
                RagChatProfileDetailState.threshold_explanation,
            ),
            spacing="5",
            wrap="wrap",
            align="start",
            width="100%",
        ),
    )


def _retrieval_item(
    label: str, value: rx.Var[str] | str, explanation: rx.Var[str] | str
) -> rx.Component:
    """One retrieval setting, with what it does rather than only what it is.

    :param label: the setting's name
    :param value: its current value
    :param explanation: what that value does to a search
    """
    return rx.vstack(
        rx.text(label, size="1", color="var(--gray-10)"),
        rx.text(value, size="4", weight="medium"),
        rx.text(explanation, size="2", color="var(--gray-11)"),
        spacing="1",
        align="start",
        max_width="24rem",
    )


def _system_prompt_section() -> rx.Component:
    """The prompt, in full — the reason this page exists at all."""
    return _section(
        "System prompt",
        "What the model is told before every question, including when to search.",
        rx.box(
            rx.text(
                RagChatProfileDetailState.profile.system_prompt,
                size="2",
                white_space="pre-wrap",
            ),
            width="100%",
            padding="1rem",
            background="var(--card-background)",
            border="1px solid var(--gray-5)",
            border_radius="var(--radius-3)",
        ),
    )


def _publication_section() -> rx.Component:
    """Whether the world can reach this profile, what that costs, and the buttons that change it.

    Publishing lives here rather than in the actions menu on purpose. It is the one action whose
    consequences have to be read before it is taken — it makes every bound knowledge base readable by
    anyone holding the token — and this is the only place with room to say so *before* the click,
    instead of in the second it takes to dismiss a confirmation.
    """
    return _section(
        "Publication",
        "A published profile answers over HTTP to anyone holding its token.",
        rx.cond(
            RagChatProfileDetailState.profile.is_published,
            rx.vstack(
                rx.hstack(
                    rx.badge("Published", color_scheme="green", variant="soft", size="2"),
                    rx.text(
                        RagChatProfileDetailState.profile_row.published_label,
                        size="2",
                        color="var(--gray-11)",
                    ),
                    align="center",
                    spacing="2",
                ),
                rx.callout(
                    "Everything the bound knowledge bases contain is readable by anyone holding "
                    "this profile's token — this version has no per-document access control. "
                    "The token was shown once, when it was minted; rotate it below if it may have "
                    "leaked, which revokes the current one immediately.",
                    size="2",
                    icon="triangle-alert",
                    color_scheme="amber",
                    width="100%",
                ),
                rx.hstack(
                    _rotate_button(),
                    _unpublish_button(),
                    spacing="3",
                ),
                spacing="3",
                align="start",
                width="100%",
            ),
            rx.vstack(
                rx.badge("Not published", color_scheme="gray", variant="soft", size="2"),
                rx.text(
                    "This profile is reachable only from inside the app. Publishing it mints a "
                    "token and makes every knowledge base it searches readable by anyone who holds "
                    "that token.",
                    size="2",
                    color="var(--gray-11)",
                ),
                _publish_button(),
                spacing="3",
                align="start",
                max_width="40rem",
            ),
        ),
        _publish_dialog(),
        _unpublish_dialog(),
        _token_dialog(),
    )


def _publish_button() -> rx.Component:
    """Opens the publish confirmation. Only rendered while the profile is not published."""
    return rx.button(
        rx.icon("globe", size=16),
        "Publish",
        on_click=lambda: RagChatProfileListState.set_action_dialog_open(
            True, ACTION_DIALOG_PUBLISH, RagChatProfileDetailState.profile_row.id
        ),
    )


def _rotate_button() -> rx.Component:
    """Opens the same confirmation as publish, which words itself for a rotation."""
    return rx.button(
        rx.icon("refresh-cw", size=16),
        "Rotate token",
        variant="soft",
        on_click=lambda: RagChatProfileListState.set_action_dialog_open(
            True, ACTION_DIALOG_PUBLISH, RagChatProfileDetailState.profile_row.id
        ),
    )


def _unpublish_button() -> rx.Component:
    """Opens the un-publish confirmation.

    This is the button that carries the un-publish spinner: its confirmation closes itself on
    confirm, so by the time the work runs there is nothing left of the dialog to show progress in.
    """
    return rx.button(
        rx.icon("globe-lock", size=16),
        "Un-publish",
        variant="soft",
        color_scheme="red",
        loading=RagChatProfileListState.busy_profile_id
        == RagChatProfileDetailState.profile_row.id,
        on_click=lambda: RagChatProfileListState.set_action_dialog_open(
            True, ACTION_DIALOG_UNPUBLISH, RagChatProfileDetailState.profile_row.id
        ),
    )


def _publish_dialog() -> rx.Component:
    """Confirm publishing this profile, or rotating its token if it is already published.

    One dialog for both because the two are mutually exclusive — a profile is either published or it
    is not — so the wording is chosen from ``is_published`` rather than by opening a different dialog.

    The confirm button is a plain button rather than an ``rx.alert_dialog.action``, which is the one
    thing here that is not decoration. This confirmation is the only one that hands over to a second
    modal — the token dialog — and ``alert_dialog.action`` closes the dialog *itself*, firing
    ``on_open_change`` as a second event racing the publish. Radix would then mount the token dialog
    while this one is still tearing down, which loses the token dialog to the click that opened it and
    leaves the body scroll lock behind, with nothing in the app clickable. Closing from
    ``publish_profile`` instead makes the hand-over one ordered sequence.
    """
    profile = RagChatProfileDetailState.profile_row
    label = rx.cond(profile.is_published, "Rotate token", "Publish")
    description = rx.cond(
        profile.is_published,
        f"'{profile.name}' is already published. Rotating mints a new token immediately — the "
        "current one stops working the moment you confirm.",
        f"Publishing '{profile.name}' makes every knowledge base it searches readable by anyone "
        "who holds its token — this version has no per-document access control. The token is shown "
        "once, right after you confirm: copy it immediately, and never paste it anywhere the "
        "documents themselves should not be readable.",
    )
    return rx.alert_dialog.root(
        rx.alert_dialog.content(
            rx.alert_dialog.title(label),
            rx.alert_dialog.description(description, margin_bottom="1rem"),
            rx.flex(
                rx.alert_dialog.cancel(rx.button("Cancel", variant="soft")),
                rx.button(
                    label,
                    loading=RagChatProfileListState.busy_profile_id == profile.id,
                    on_click=lambda: RagChatProfileListState.publish_profile(profile.id),
                ),
                spacing="3",
                justify="end",
            ),
        ),
        open=is_action_dialog_open(profile.id, ACTION_DIALOG_PUBLISH),
        on_open_change=lambda is_open: RagChatProfileListState.set_action_dialog_open(
            is_open, ACTION_DIALOG_PUBLISH, profile.id
        ),
    )


def _token_dialog() -> rx.Component:
    """The token just minted by a publish or a rotation, shown exactly once.

    Lives on this page because publishing does: it is the second half of the hand-over
    ``publish_profile`` sequences, and there is nowhere else it could be opened from.

    Closing it does not revoke anything — the profile stays published — it only stops the token from
    being displayed again.

    Copying is a real button in the footer rather than ``rx.code_block``'s floating overlay one: the
    token is a single unbroken 50-character string, so an overlay sits on top of the characters it is
    meant to help with. The button also confirms with a toast, because a copy that silently did
    nothing is indistinguishable from one that worked, and this is the only chance to get it.
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
                rx.code(
                    RagChatProfileListState.minted_token,
                    size="2",
                    variant="soft",
                    color_scheme="gray",
                    width="100%",
                    display="block",
                    padding="0.75rem",
                    # The token has no spaces to wrap on, so it has to be allowed to break anywhere
                    # or it overflows the dialog.
                    word_break="break-all",
                    white_space="normal",
                ),
                spacing="3",
                width="100%",
            ),
            rx.hstack(
                rx.spacer(),
                rx.button(
                    "Done",
                    variant="soft",
                    on_click=RagChatProfileListState.close_token_dialog,
                ),
                rx.button(
                    rx.icon("copy", size=14),
                    "Copy token",
                    on_click=[
                        rx.set_clipboard(RagChatProfileListState.minted_token),
                        rx.toast.success("Token copied to the clipboard."),
                    ],
                ),
                spacing="3",
                width="100%",
                margin_top="1rem",
            ),
            on_interact_outside=RagChatProfileListState.close_token_dialog,
            on_escape_key_down=RagChatProfileListState.close_token_dialog,
            max_width="32rem",
        ),
        open=RagChatProfileListState.token_dialog_open,
    )


def _unpublish_dialog() -> rx.Component:
    """Confirm un-publishing — revokes access for anyone holding the current token immediately."""
    profile = RagChatProfileDetailState.profile_row
    return rx.alert_dialog.root(
        rx.alert_dialog.content(
            rx.alert_dialog.title("Un-publish chat profile"),
            rx.alert_dialog.description(
                f"Anyone holding the current token for '{profile.name}' loses access immediately. "
                "The profile itself is kept, and can be published again later with a new token.",
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
        open=is_action_dialog_open(profile.id, ACTION_DIALOG_UNPUBLISH),
        on_open_change=lambda is_open: RagChatProfileListState.set_action_dialog_open(
            is_open, ACTION_DIALOG_UNPUBLISH, profile.id
        ),
    )


def _not_found_message() -> rx.Component:
    """What the page says when the route names a profile that is not there."""
    return rx.cond(
        RagChatProfileDetailState.is_loading,
        rx.center(rx.spinner(size="3"), width="100%", padding="3rem"),
        rx.vstack(
            rx.icon("circle-alert", size=28, color="var(--gray-8)"),
            rx.text("This chat profile does not exist.", size="2", weight="medium"),
            rx.button(
                "Back to chat profiles",
                on_click=rx.redirect(CHAT_PROFILES_ROUTE),
            ),
            align="center",
            spacing="3",
            width="100%",
            padding="3rem 1rem",
        ),
    )
