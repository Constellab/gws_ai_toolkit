import reflex as rx

from .ai_table_plot_file_chat_config_state import AiTablePlotFileChatConfigState


def ai_table_plot_file_chat_config_component() -> rx.Component:
    """AI Table Plot File configuration interface component.

    This component provides a simplified form-based interface for configuring
    AI Table Plot File settings. Unlike the plot_agent version, this does not
    include system prompt editing as the prompt is fixed for plot_file mode.

    Features:
        - Model and temperature configuration with validation
        - Real-time form validation and error feedback
        - Success/error toast notifications
        - Simplified interface without system prompt editing

    The component uses AiTablePlotFileChatConfigState for state management, which handles:
        - Configuration loading and saving (model and temperature only)
        - Form validation and submission
        - Integration with the application configuration system

    Note:
        The system prompt is fixed and not configurable for plot_file mode as it
        uses direct file upload to OpenAI with specific analysis capabilities.

    Returns:
        rx.Component: Complete configuration interface with form fields, validation,
            explanatory text, and submission handling for AI Table Plot File settings.

    Example:
        config_ui = ai_table_plot_file_chat_config_component()
        # Renders a configuration form for AI Table Plot File settings
    """
    return rx.vstack(
        rx.heading("AI Table Plot File Configuration"),
        rx.text("Configure AI settings for Excel/CSV data analysis with file upload.", color="gray"),
        rx.text("Note: System prompt is fixed and optimized for file analysis.", color="orange", style={"font_style": "italic"}),

        # Configuration modification form
        rx.form(
            rx.vstack(

                rx.heading("Model Configuration", size="4", margin_top="1em"),
                rx.text("OpenAI model to use for data analysis responses:", color="gray"),
                rx.input(
                    placeholder="Enter model name (e.g., gpt-4o, gpt-4o-mini)...",
                    name="model",
                    default_value=AiTablePlotFileChatConfigState.model,
                    width="100%",
                ),

                rx.heading("Temperature", size="4", margin_top="4"),
                rx.text("Controls randomness: 0.0 = focused, 2.0 = creative", color="gray"),
                rx.input(
                    placeholder="0.7",
                    name="temperature",
                    default_value=rx.cond(
                        AiTablePlotFileChatConfigState.temperature,
                        AiTablePlotFileChatConfigState.temperature.to(str),
                        "0.7"
                    ),
                    type="number",
                    min=0.0,
                    max=2.0,
                    step=0.1,
                    width="100%",
                ),

                rx.button(
                    "Update Configuration",
                    type="submit",
                    color_scheme="blue",
                    cursor="pointer"
                ),
                spacing="3",
                width="100%"
            ),
            on_submit=AiTablePlotFileChatConfigState.handle_config_form_submit,
            width="100%"
        ),
        spacing="0",
        width="100%",
    )