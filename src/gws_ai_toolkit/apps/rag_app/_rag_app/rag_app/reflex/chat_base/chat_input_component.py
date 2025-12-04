import reflex as rx

from .chat_config import ChatConfig


def chat_input_component(config: ChatConfig) -> rx.Component:
    """Generic input component - uses chat page styling"""

    return rx.form(
        rx.input(
            placeholder=config.state.placeholder_text,
            name="message",
            flex="1",
            disabled=config.state.is_streaming,
            border_radius="24px",
            style={"input": {"padding-inline": "12px"}},
            size="3",
        ),
        # rx.box(width="34px", height="34px", flex_shrink="0"),  # Spacer to align with non-dense input
        rx.box(
            rx.button(
                rx.icon("send", size=18),
                type="submit",
                disabled=config.state.is_streaming,
                variant="ghost",
                size="3",
                border_radius="50%",
                padding="8px",
            ),
            padding="8px",
            flex_shrink="0",
            margin_left="0.5em",
            display="flex",
        ),
        on_submit=config.state.submit_input_form,
        reset_on_submit=True,
        display="flex",
        flex_direction="row",
        align_items="center",
    )
