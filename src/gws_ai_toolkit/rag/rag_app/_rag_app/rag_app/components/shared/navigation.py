import reflex as rx


def navigation() -> rx.Component:
    """Navigation component for switching between pages."""
    return rx.hstack(
        rx.link(
            rx.button(
                rx.icon("message-circle", size=16),
                "Chat",
                variant="ghost",
                color_scheme="blue",
            ),
            href="/",
        ),
        rx.link(
            rx.button(
                rx.icon("settings", size=16),
                "Config",
                variant="ghost",
                color_scheme="blue",
            ),
            href="/config",
        ),
        spacing="2",
        p="3",
        border_bottom="1px solid",
        border_color="gray.200",
        width="100%",
    )