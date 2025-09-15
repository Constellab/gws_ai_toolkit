

from typing import List

import reflex as rx

from .nav_bar_component import NavBarItem, nav_bar_component


def page_component(nav_bar_items: List[NavBarItem],
                   content: rx.Component,
                   disable_padding: bool = False) -> rx.Component:
    """Wrap the page content with navigation and layout."""
    return rx.vstack(
        nav_bar_component(nav_bar_items),
        rx.box(
            content,
            display="flex",
            width="100%",
            flex="1",
            padding="1em" if not disable_padding else "0",
            min_height="0",
        ),
        spacing="0",
        width="100%",
        height="100vh",
    )
