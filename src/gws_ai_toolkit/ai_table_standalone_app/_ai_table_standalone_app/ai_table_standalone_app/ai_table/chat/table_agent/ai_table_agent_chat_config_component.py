import reflex as rx

from .ai_table_agent_chat_config_state import AiTableAgentChatConfigState


def ai_table_agent_chat_config_component() -> rx.Component:
    """AI Table Agent configuration interface component.

    This component provides a form-based interface for configuring AI Table Agent
    settings including AI model parameters for the unified table operations agent.
    It offers real-time validation and user-friendly explanations for each configuration option.

    The Table Agent combines both plotting and transformation capabilities through
    intelligent function calling, requiring optimal model and temperature settings
    for effective request routing and sub-agent delegation.

    Features:
        - Model and temperature configuration optimized for function calling
        - Real-time form validation and error feedback
        - Success/error toast notifications
        - Guidance for optimal settings for unified operations

    The component uses AiTableTableAgentChatConfigState for state management, which handles:
        - Configuration loading and saving
        - Form validation and submission
        - Integration with the application configuration system

    Returns:
        rx.Component: Complete configuration interface with form fields, validation,
            explanatory text, and submission handling for all AI Table Agent settings.

    Example:
        config_ui = ai_table_table_agent_chat_config_component()
        # Renders a configuration form for unified AI Table Agent settings
    """
    return rx.vstack(
        rx.heading("AI Table Agent Configuration"),
        rx.text(
            "Configure AI settings for unified table operations with intelligent routing between plotting and transformation capabilities.",
            color="gray"
        ),

        # Configuration modification form
        rx.form(
            rx.vstack(

                rx.heading("Model Configuration", size="4", margin_top="1em"),
                rx.text(
                    "OpenAI model to use for intelligent request routing and function calling:",
                    color="gray"
                ),
                rx.input(
                    placeholder="Enter model name (e.g., gpt-4o, gpt-4o-mini)...",
                    name="model",
                    default_value=AiTableAgentChatConfigState.model,
                    width="100%",
                ),

                rx.heading("Temperature", size="4", margin_top="4"),
                rx.text(
                    "Controls randomness: Lower values (0.1-0.3) recommended for precise function calling",
                    color="gray"
                ),
                rx.input(
                    placeholder="0.3",
                    name="temperature",
                    default_value=rx.cond(
                        AiTableAgentChatConfigState.temperature,
                        AiTableAgentChatConfigState.temperature.to_string(),
                        "0.3"
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
            on_submit=AiTableAgentChatConfigState.handle_config_form_submit,
            width="100%"
        ),
        spacing="0",
        width="100%",
    )
