from typing import Literal

import reflex as rx
from gws_ai_toolkit.models.chat.conversation.base_chat_conversation import ChatConversationMode

ChipSize = Literal["normal", "big"]


def conversation_mode_chip_reactive(mode: rx.Var[str], size: ChipSize = "normal") -> rx.Component:
    """A reactive version of :func:`conversation_mode_chip` for use with ``rx.foreach``.

    Uses ``rx.match`` to dispatch on the reactive *mode* var.
    Recognised values: ``"rag_chat"`` / ``"rag"`` (tertiary) and
    ``"ai_expert"`` (secondary).  Unknown values fall back to a plain badge.

    :param mode: Reactive var containing the conversation mode string.
    :param size: Chip size — ``"normal"`` or ``"big"``.
    :return: The chip component.
    """
    badge_size = "3" if size == "big" else "2"
    return rx.match(
        mode,
        (
            ChatConversationMode.RAG.value,
            _chip("Chat", "message-circle", color_prefix="tertiary", size=badge_size),
        ),
        (
            ChatConversationMode.AI_EXPERT.value,
            _chip("AI Expert", "brain", color_prefix="secondary", size=badge_size),
        ),
        rx.badge(mode.replace("_", " ").title(), size=badge_size, variant="soft"),
    )


def conversation_mode_chip_switchable(
    current_mode: str,
    size: ChipSize = "big",
) -> rx.Component:
    """A mode chip with a popover to switch to the other mode.

    When clicked, shows a popover with a button to navigate to the other mode's page.

    :param current_mode: The current conversation mode string (use ChatConversationMode values).
    :param size: Chip size — ``"normal"`` or ``"big"``.
    :return: The chip component wrapped in a popover.
    """
    badge_size = "3" if size == "big" else "2"

    if current_mode == ChatConversationMode.RAG.value:
        chip = _chip("Chat", "message-circle", color_prefix="tertiary", size=badge_size)
        switch_icon = "brain"
        switch_label = "Switch to AI Expert"
        switch_href = "/ai-expert"
    else:
        chip = _chip("AI Expert", "brain", color_prefix="secondary", size=badge_size)
        switch_icon = "message-circle"
        switch_label = "Switch to Chat"
        switch_href = "/"

    return rx.popover.root(
        rx.popover.trigger(
            rx.box(
                chip,
                cursor="pointer",
                _hover={"opacity": "0.8"},
                transition="opacity 0.15s ease",
            ),
        ),
        rx.popover.content(
            rx.link(
                rx.hstack(
                    rx.icon(switch_icon, size=14),
                    rx.text(switch_label, size="2", weight="medium"),
                    align="center",
                    spacing="2",
                    padding="4px 8px",
                    border_radius="6px",
                    _hover={"background": "var(--gray-3)"},
                    width="100%",
                ),
                href=switch_href,
                text_decoration="none",
                color="inherit",
                width="100%",
            ),
            side="bottom",
            align="start",
        ),
    )


def _chip(label: str, icon: str, color_prefix: str, size: str = "2") -> rx.Component:
    """Internal helper that renders a pill chip using custom CSS color variables.

    :param label: Text shown inside the chip.
    :param icon: Lucide icon name.
    :param color_prefix: CSS variable prefix ("secondary" or "tertiary").
    :param size: Radix badge size ("2" normal, "3" big).
    :return: The styled chip component.
    """
    icon_size = 16 if size == "3" else 14
    return rx.badge(
        rx.icon(icon, size=icon_size),
        label,
        variant="soft",
        size=size,
        background=f"var(--{color_prefix}-3)",
        color=f"var(--{color_prefix}-11)",
    )
