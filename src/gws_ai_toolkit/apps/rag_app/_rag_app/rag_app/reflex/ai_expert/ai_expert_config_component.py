import reflex as rx

from .ai_expert_config_state import AiExpertConfigState


def ai_expert_config_component() -> rx.Component:
    """AI Expert configuration interface component.

    This component provides a comprehensive form-based interface for configuring
    all AI Expert settings including processing modes, AI model parameters, and
    system prompts. It offers real-time validation and user-friendly explanations
    for each configuration option.

    Features:
        - Interactive mode selection (full_text_chunk, relevant_chunks, full_file)
        - Dynamic form fields that show/hide based on selected mode
        - Model and temperature configuration with validation
        - System prompt editing with placeholder validation
        - Chunk count configuration for relevant_chunks mode
        - Real-time form validation and error feedback
        - Success/error toast notifications

    The component uses AiExpertConfigState for state management, which handles:
        - Configuration loading and saving
        - Form validation and submission
        - Dynamic field visibility based on mode selection
        - Integration with the application configuration system

    Returns:
        rx.Component: Complete configuration interface with form fields, validation,
            explanatory text, and submission handling for all AI Expert settings.

    Example:
        config_ui = ai_expert_config_component()
        # Renders a full configuration form with all AI Expert settings
    """
    return rx.vstack(
        rx.heading("AI Expert Configuration"),
        # Configuration modification form
        rx.vstack(
            rx.form(
                rx.vstack(
                    rx.heading("AI Mode", size="4"),
                    rx.text("Choose how the AI processes documents:", color="gray"),
                    rx.radio(
                        ["full_text_chunk", "relevant_chunks", "full_file"],
                        name="mode",
                        default_value=AiExpertConfigState.current_mode,
                        on_change=AiExpertConfigState.on_mode_change,
                        direction="column",
                        spacing="3",
                    ),
                    rx.vstack(
                        rx.text(
                            "• full_text_chunk: Document content (all chunks) is converted to text and integrated into the chat prompt. Fast and efficient for text-based analysis.",
                            size="2",
                            color="gray",
                        ),
                        rx.text(
                            "• relevant_chunks: Only the most relevant chunks based on your question are retrieved and used. More targeted and efficient.",
                            size="2",
                            color="gray",
                        ),
                        rx.text(
                            "• full_file: Original file is uploaded to AI with access to the complete document structure. Better for complex documents with formatting, images, or tables.",
                            size="2",
                            color="gray",
                        ),
                        spacing="2",
                        margin_left="2",
                    ),
                    # Conditional field for chunk count when relevant_chunks mode is selected
                    rx.cond(
                        AiExpertConfigState.show_max_chunk_config,
                        rx.vstack(
                            rx.text("Max number of chunks (1-100):", color="gray"),
                            rx.input(
                                placeholder="5",
                                name="max_chunks",
                                default_value=rx.cond(
                                    AiExpertConfigState.max_chunks,
                                    AiExpertConfigState.max_chunks.to(str),
                                    "5",
                                ),
                                type="number",
                                min=1,
                                max=100,
                                width="100%",
                            ),
                            spacing="2",
                        ),
                    ),
                    rx.heading("Model Configuration", size="4", margin_top="4"),
                    rx.text("OpenAI model to use for AI responses:", color="gray"),
                    rx.input(
                        placeholder="Enter model name (e.g., gpt-4o, gpt-4o-mini)...",
                        name="model",
                        default_value=AiExpertConfigState.model,
                        width="100%",
                    ),
                    rx.heading("Temperature", size="4", margin_top="4"),
                    rx.text("Controls randomness: 0.0 = focused, 2.0 = creative", color="gray"),
                    rx.input(
                        placeholder="0.7",
                        name="temperature",
                        default_value=rx.cond(
                            AiExpertConfigState.temperature,
                            AiExpertConfigState.temperature.to(str),
                            "0.7",
                        ),
                        type="number",
                        min=0.0,
                        max=2.0,
                        step=0.1,
                        width="100%",
                    ),
                    rx.heading("System prompt", size="4", margin_top="4"),
                    rx.text(f"Use '{AiExpertConfigState.prompt_file_id_placeholder}' placeholder."),
                    rx.text_area(
                        placeholder="Enter new system prompt...",
                        name="system_prompt",
                        default_value=AiExpertConfigState.system_prompt,
                        resize="vertical",
                        rows="15",
                        width="100%",
                    ),
                    rx.button("Update Configuration", type="submit", color_scheme="blue"),
                    spacing="3",
                    width="100%",
                ),
                on_submit=AiExpertConfigState.handle_config_form_submit,
                width="100%",
                on_mount=AiExpertConfigState.on_form_mount,
            ),
            spacing="3",
            width="100%",
        ),
        spacing="6",
        width="100%",
    )
