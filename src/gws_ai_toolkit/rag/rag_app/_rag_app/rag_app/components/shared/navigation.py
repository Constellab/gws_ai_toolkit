import reflex as rx


def navbar_link(text: str, icon: str, url: str) -> rx.Component:
    return rx.link(
        rx.hstack(
            rx.icon(icon, size=16),
            rx.text(text, size="4", weight="medium"),
            align_items="center"
        ),
        href=url
    )


def navigation() -> rx.Component:
    """Navigation component for switching between pages."""
    return rx.box(
        rx.hstack(
            navbar_link("Chat", "message-circle", "/"),
            navbar_link("Resources", "database", "/resource"),
            navbar_link("Config", "settings", "/config"),
            spacing="5",
            align_items="center",
        ),
        bg=rx.color("accent", 3),
        padding="1em",
        width="100%",
    )
