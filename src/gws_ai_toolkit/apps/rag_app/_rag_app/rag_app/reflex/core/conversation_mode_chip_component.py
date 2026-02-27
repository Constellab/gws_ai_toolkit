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
