import reflex as rx
from gws_reflex_base import render_main_container

from ..components.config.resource_selector import resource_selector
from ..components.config.sync_controls import sync_controls
from ..components.shared.navigation import navigation


def config_page() -> rx.Component:
    """Configuration page component."""
    return render_main_container(
        rx.vstack(
            navigation(),
            rx.container(
                rx.vstack(
                    sync_controls(),
                    rx.divider(),
                    resource_selector(),
                    spacing="6",
                    align="start",
                ),
                max_width="1200px",
                p="4",
            ),
            spacing="0",
            min_height="100vh",
        )
    )
