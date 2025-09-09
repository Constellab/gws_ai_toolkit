
import reflex as rx

from .reflex import ai_expert_config_component, ai_table_chat_config_component


def combined_config_page() -> rx.Component:
    """Combined Configuration page component with both AI Expert and AI Table settings using tabs."""
    return rx.vstack(
        rx.tabs.root(
            rx.tabs.list(
                rx.tabs.trigger("AI Expert", value="ai_expert", cursor="pointer",),
                rx.tabs.trigger("AI Table", value="ai_table", cursor="pointer",),
            ),

            rx.tabs.content(
                rx.vstack(
                    ai_expert_config_component(),
                    spacing="4",
                    width="100%",
                ),
                value="ai_expert",
                padding_top="1em",
                padding_bottom="1em",
            ),

            rx.tabs.content(
                rx.vstack(
                    ai_table_chat_config_component(),
                    spacing="4",
                    width="100%",
                ),
                value="ai_table",
                padding_top="1em",
                padding_bottom="1em",
            ),

            default_value="ai_expert",
            width="100%",
        ),

        spacing="6",
        width="100%",
    )
