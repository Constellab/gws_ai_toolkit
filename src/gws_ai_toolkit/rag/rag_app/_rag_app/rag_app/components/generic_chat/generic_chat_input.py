import reflex as rx

from .chat_config import ChatConfig, ChatStateBase


def generic_chat_input(state: ChatStateBase) -> rx.Component:
    """Generic input component - uses chat page styling"""

    return rx.form(
        rx.hstack(
            rx.input(
                placeholder=state.placeholder_text,
                name="message",
                flex="1",
                disabled=state.is_streaming,
                border_radius="24px",
                style={'input': {'padding-inline': '12px'}},
                size="3"
            ),
            rx.button(
                rx.icon("send", size=18),
                type="submit",
                disabled=state.is_streaming,
                cursor="pointer",
                variant="ghost",
                padding="8px",
                size="3",
                border_radius="50%"
            ),
            width="100%",
            spacing="5",
            align_items="center"
        ),
        on_submit=state.submit_input_form,
        reset_on_submit=True,
    )
