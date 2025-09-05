
import reflex as rx

from .ai_table_config_state import AiTableConfigState


def ai_table_config_component() -> rx.Component:
    """AI Table configuration interface component.

    This component provides a form-based interface for configuring AI Table
    settings including AI model parameters and system prompts. It offers
    real-time validation and user-friendly explanations for each configuration option.

    Features:
        - Model and temperature configuration with validation
        - System prompt editing with placeholder validation
        - Real-time form validation and error feedback
        - Success/error toast notifications

    The component uses AiTableConfigState for state management, which handles:
        - Configuration loading and saving
        - Form validation and submission
        - Integration with the application configuration system

    Note:
        Unlike AI Expert, this component does not include mode selection or
        max_chunks configuration as AI Table only operates in full_file mode
        for Excel/CSV analysis.

    Returns:
        rx.Component: Complete configuration interface with form fields, validation,
            explanatory text, and submission handling for all AI Table settings.

    Example:
        config_ui = ai_table_config_component()
        # Renders a configuration form for AI Table settings
    """
    return rx.vstack(
        rx.heading("AI Table Configuration"),
        rx.text("Configure AI settings for Excel/CSV data analysis.", color="gray"),

        # Configuration modification form
        rx.form(
            rx.vstack(

                rx.heading("Model Configuration", size="4", margin_top="1em"),
                rx.text("OpenAI model to use for data analysis responses:", color="gray"),
                rx.input(
                    placeholder="Enter model name (e.g., gpt-4o, gpt-4o-mini)...",
                    name="model",
                    default_value=AiTableConfigState.model,
                    width="100%",
                ),

                rx.heading("Temperature", size="4", margin_top="4"),
                rx.text("Controls randomness: 0.0 = focused, 2.0 = creative", color="gray"),
                rx.input(
                    placeholder="0.7",
                    name="temperature",
                    default_value=rx.cond(
                        AiTableConfigState.temperature,
                        AiTableConfigState.temperature.to(str),
                        "0.7"
                    ),
                    type="number",
                    min=0.0,
                    max=2.0,
                    step=0.1,
                    width="100%",
                ),

                rx.heading("System prompt", size="4", margin_top="4"),
                rx.text(f"Use '{AiTableConfigState.prompt_file_id_placeholder}' placeholder for the file."),
                rx.text_area(
                    placeholder="Enter new system prompt...",
                    name="system_prompt",
                    default_value=AiTableConfigState.system_prompt,
                    resize="vertical",
                    rows="15",
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
            on_submit=AiTableConfigState.handle_config_form_submit,
            width="100%"
        ),
        spacing="0",
        width="100%",
        class_name="aiiiii"
    )
