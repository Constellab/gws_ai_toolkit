import reflex as rx

from .reflex.ai_expert.ai_expert_config_component import ai_expert_config_component
from .reflex.rag_chat.rag_chat_config_component import rag_chat_config_component


def combined_config_page() -> rx.Component:
    """Combined Configuration page component with RAG Chat, AI Expert and AI Table settings using tabs."""
    return rx.vstack(
        rx.tabs.root(
            rx.tabs.list(
                rx.tabs.trigger(
                    "RAG Chat",
                    value="rag_chat",
                    cursor="pointer",
                ),
                rx.tabs.trigger(
                    "AI Expert",
                    value="ai_expert",
                    cursor="pointer",
                ),
            ),
            rx.tabs.content(
                rx.vstack(
                    rag_chat_config_component(),
                    spacing="4",
                    width="100%",
                ),
                value="rag_chat",
                padding_top="1em",
                padding_bottom="1em",
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
            default_value="rag_chat",
            width="100%",
        ),
        spacing="6",
        width="100%",
    )
