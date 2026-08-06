"""One fact of a detail page's summary row.

Both detail pages open with a strip of the handful of facts that decide what the thing on screen will
actually do — a knowledge base's document count and chunking policy, a chat profile's model and
retrieval settings. One helper, so the two strips cannot drift apart in icon size, spacing, or which
of the two lines is the value and which is the label.
"""

import reflex as rx


def summary_item(icon: str, value: rx.Var[str] | str, label: str) -> rx.Component:
    """One fact of a summary row: an icon, the value, and what the value means.

    :param icon: lucide icon name
    :param value: the value to show, reactive or literal
    :param label: what the value means
    """
    return rx.hstack(
        rx.icon(icon, size=24, color="var(--gray-9)"),
        rx.vstack(
            rx.text(value, size="2", weight="medium"),
            rx.text(label, size="1", color="var(--gray-10)"),
            spacing="0",
        ),
        align="center",
        spacing="2",
    )
