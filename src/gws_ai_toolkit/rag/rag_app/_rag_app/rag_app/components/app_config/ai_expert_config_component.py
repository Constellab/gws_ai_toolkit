

import reflex as rx

from gws_ai_toolkit.rag.rag_app._rag_app.rag_app.pages.ai_expert_page.ai_expert_state import \
    AiExpertState


def show_ai_expert_config_section():
    """Show the AI Expert configuration section."""
    return rx.vstack(
        rx.heading("AI Expert Configuration"),

        # Configuration modification form
        rx.vstack(
            rx.heading("System prompt", size="4"),
            rx.text("Use '[FILE_ID]' placeholder."),
            rx.form(
                rx.vstack(
                    rx.text_area(
                        placeholder="Enter new system prompt...",
                        name="system_prompt",
                        default_value=AiExpertState.system_prompt,
                        resize="vertical",
                        rows="20",
                        width="100%",
                    ),
                    rx.button(
                        "Update Configuration",
                        type="submit",
                        color_scheme="blue"
                    ),
                    spacing="3",
                    width="100%"
                ),
                on_submit=AiExpertState.handle_config_form_submit,
                width="100%"
            ),
            spacing="3",
            width="100%"
        ),

        spacing="6",
        width="100%"
    )
