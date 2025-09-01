

import reflex as rx

from gws_ai_toolkit.rag.rag_app._rag_app.rag_app.components.app_config.ai_expert_config_state import \
    AiExpertConfigState


def show_ai_expert_config_section():
    """Show the AI Expert configuration section."""
    return rx.vstack(
        rx.heading("AI Expert Configuration"),

        # Configuration modification form
        rx.vstack(
            rx.form(
                rx.vstack(
                    rx.heading("AI Mode", size="4"),
                    rx.text("Choose how the AI processes documents:", color="gray"),
                    rx.radio(
                        ["text_chunk", "full_file"],
                        name="mode",
                        default_value=AiExpertConfigState.current_mode,
                        direction="column",
                        spacing="3",
                    ),
                    rx.vstack(
                        rx.text(
                            "• text_chunk: Document content is converted to text and integrated into the chat prompt. Fast and efficient for text-based analysis.",
                            size="2",
                            color="gray"
                        ),
                        rx.text(
                            "• full_file: Original file is uploaded to AI with access to the complete document structure. Better for complex documents with formatting, images, or tables.",
                            size="2",
                            color="gray"
                        ),
                        spacing="2",
                        margin_left="2"
                    ),
                    rx.heading("System prompt", size="4", margin_top="4"),
                    rx.text(f"Use '{AiExpertConfigState.prompt_file_id_placeholder}' placeholder."),
                    rx.text_area(
                        placeholder="Enter new system prompt...",
                        name="system_prompt",
                        default_value=AiExpertConfigState.system_prompt,
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
                on_submit=AiExpertConfigState.handle_config_form_submit,
                width="100%"
            ),
            spacing="3",
            width="100%"
        ),

        spacing="6",
        width="100%"
    )
