import reflex as rx

from .ai_table_plot_agent_chat_config_state import \
    AiTablePlotAgentChatConfigState


def ai_table_plot_agent_chat_config_component() -> rx.Component:
    """AI Table Plot Agent configuration interface component.

    This component provides a form-based interface for configuring AI Table Plot Agent
    settings including AI model parameters. It offers
    real-time validation and user-friendly explanations for each configuration option.

    Features:
        - Model and temperature
        - Real-time form validation and error feedback
        - Success/error toast notifications

    The component uses AiTablePlotAgentChatConfigState for state management, which handles:
        - Configuration loading and saving
        - Form validation and submission
        - Integration with the application configuration system

    Returns:
        rx.Component: Complete configuration interface with form fields, validation,
            explanatory text, and submission handling for all AI Table Plot Agent settings.

    Example:
        config_ui = ai_table_plot_agent_chat_config_component()
        # Renders a configuration form for AI Table Plot Agent settings
    """
    return rx.vstack(
        rx.heading("AI Table Plot Agent Configuration"),
        rx.text("Configure AI settings for Excel/CSV data analysis with plot generation.", color="gray"),

        # Configuration modification form
        rx.form(
            rx.vstack(

                rx.heading("Model Configuration", size="4", margin_top="1em"),
                rx.text("OpenAI model to use for data analysis responses:", color="gray"),
                rx.input(
                    placeholder="Enter model name (e.g., gpt-4o, gpt-4o-mini)...",
                    name="model",
                    default_value=AiTablePlotAgentChatConfigState.model,
                    width="100%",
                ),

                rx.heading("Temperature", size="4", margin_top="4"),
                rx.text("Controls randomness: 0.0 = focused, 2.0 = creative", color="gray"),
                rx.input(
                    placeholder="0.7",
                    name="temperature",
                    default_value=rx.cond(
                        AiTablePlotAgentChatConfigState.temperature,
                        AiTablePlotAgentChatConfigState.temperature.to_string(),
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
            on_submit=AiTablePlotAgentChatConfigState.handle_config_form_submit,
            width="100%"
        ),
        spacing="0",
        width="100%",
    )
