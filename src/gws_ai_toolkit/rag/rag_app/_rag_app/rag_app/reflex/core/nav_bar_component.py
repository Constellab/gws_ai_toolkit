from dataclasses import dataclass
from typing import List

import reflex as rx


@dataclass
class NavBarItem():
    text: str
    icon: str
    url: str


def _navbar_link(item: NavBarItem) -> rx.Component:
    return rx.link(
        rx.hstack(
            rx.icon(item.icon, size=16),
            rx.text(item.text, size="4", weight="medium"),
            align_items="center"
        ),
        href=item.url
    )


def nav_bar_component(items: List[NavBarItem]) -> rx.Component:
    """Navigation component for switching between pages."""
    return rx.box(
        rx.hstack(
            *[_navbar_link(item) for item in items],
            spacing="5",
            align_items="center",
        ),
        bg=rx.color("accent", 3),
        padding="1em",
        width="100%",
    )
