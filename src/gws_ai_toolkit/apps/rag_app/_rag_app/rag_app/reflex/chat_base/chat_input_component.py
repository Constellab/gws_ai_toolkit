import reflex as rx

from .chat_config import ChatConfig

# JavaScript to submit form on Enter key press without Shift
submit_script = """
{
if(event.key === 'Enter' && !event.shiftKey) {
    event.preventDefault();
    document.getElementById('chat-input-form').requestSubmit();
}
}
"""


def chat_input_component(config: ChatConfig, hide_border: bool = False) -> rx.Component:
    """Generic input component - uses chat page styling"""

    return rx.form(
        rx.text_area(
            placeholder=config.state.placeholder_text,
            name="message",
            flex="1",
            disabled=config.state.is_streaming,
            border_radius="24px",
            size="3",
            rows="1",
            max_height="200px",
            min_height="initial",
            overflow_y="auto",
            class_name=rx.cond(hide_border, "hide-border", ""),
            on_key_down=rx.run_script(
                # remove newlines and extra spaces
                submit_script.strip().replace("\n", "").replace("    ", "")
            ),
            style={
                "& textarea": {
                    # make the textarea auto-resize
                    "field-sizing": "content",
                    "padding": "12px 16px",
                },
                "&.hide-border": {
                    "box_shadow": "none",
                    "outline": "none",
                },
            },
        ),
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
            height="48px",
            display="flex",
            align_items="center",
            align_self="flex-end",
        ),
        on_submit=config.state.submit_input_form,
        reset_on_submit=True,
        id="chat-input-form",
        display="flex",
        flex_direction="row",
        align_items="flex-end",
    )
