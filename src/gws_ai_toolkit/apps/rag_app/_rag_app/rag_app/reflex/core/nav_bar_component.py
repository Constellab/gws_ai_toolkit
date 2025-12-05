from dataclasses import dataclass

import reflex as rx


@dataclass
class NavBarItem:
    text: str
    icon: str
    url: str


def _navbar_link(item: NavBarItem) -> rx.Component:
    # Compare paths, normalizing both to handle '/' correctly
    current_path = rx.State.router.page.path

    # Match '/' with '/index' or exact match, and handle sub-pages
    is_current = rx.cond(
        item.url == "/",
        (current_path == "/") | (current_path == "/index"),
        current_path.startswith(item.url),
    )

    return rx.link(
        rx.hstack(
            rx.icon(item.icon, size=16),
            rx.text(item.text, size="4", weight="medium"),
            align_items="center",
            padding="0.5em 1em",
            color=rx.cond(
                is_current,
                rx.color("accent", 11),
                rx.color("gray", 11),
            ),
            border_bottom=rx.cond(
                is_current,
                f"2px solid {rx.color('accent', 9)}",
                "2px solid transparent",
            ),
            transition="all 0.2s ease",
            _hover={
                "color": rx.color("accent", 10),
            },
        ),
        href=item.url,
        text_decoration="none",
    )


def nav_bar_component(items: list[NavBarItem]) -> rx.Component:
    """Navigation component for switching between pages."""
    return rx.box(
        rx.hstack(
            rx.foreach(
                items,
                _navbar_link,
            ),
            spacing="5",
            align_items="center",
        ),
        bg=rx.color("accent", 3),
        padding="0.5em",
        width="100%",
        key="nav-bar",
    )
