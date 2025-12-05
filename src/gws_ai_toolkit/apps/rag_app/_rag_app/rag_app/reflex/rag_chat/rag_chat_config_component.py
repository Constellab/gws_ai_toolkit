import reflex as rx

from .rag_chat_config_state import RagChatConfigState


def rag_chat_config_component() -> rx.Component:
    """RAG Chat configuration interface component.

    This component provides a form-based interface for configuring
    RAG Chat settings including placeholder text for the chat input field.
    It offers real-time validation and user-friendly explanations
    for each configuration option.

    Features:
        - Placeholder text configuration with validation
        - Real-time form validation and error feedback
        - Success/error toast notifications

    The component uses RagChatConfigState for state management, which handles:
        - Configuration loading and saving
        - Form validation and submission
        - Integration with the application configuration system

    Returns:
        rx.Component: Complete configuration interface with form fields, validation,
            explanatory text, and submission handling for RAG Chat settings.

    Example:
        config_ui = rag_chat_config_component()
        # Renders a configuration form with RAG Chat settings
    """
    return rx.vstack(
        rx.heading("RAG Chat Configuration"),
        # Configuration modification form
        rx.vstack(
            rx.form(
                rx.vstack(
                    rx.heading("Placeholder text", size="4", margin_top="4"),
                    rx.text("Text shown in the chat input field:", color="gray"),
                    rx.input(
                        placeholder="Ask a question...",
                        name="placeholder_text",
                        default_value=RagChatConfigState.placeholder_text,
                        width="100%",
                    ),
                    rx.button("Update Configuration", type="submit", color_scheme="blue"),
                    spacing="3",
                    width="100%",
                ),
                on_submit=RagChatConfigState.handle_config_form_submit,
                width="100%",
            ),
            spacing="3",
            width="100%",
        ),
        spacing="6",
        width="100%",
    )
