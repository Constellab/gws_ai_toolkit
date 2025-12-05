from gws_core import BaseModelDTO


class RagChatConfig(BaseModelDTO):
    """Configuration class for RAG Chat functionality.

    This class defines all configurable parameters for the RAG Chat system,
    including placeholder text for the chat input field. It extends
    BaseModelDTO to provide serialization and validation capabilities.

    Attributes:
        placeholder_text (str): Placeholder text shown in the chat input field.
            Default: "Ask a question..."

    Example:
        config = RagChatConfig(
            placeholder_text="Ask me anything about your documents..."
        )
    """

    # Placeholder text for the chat input field
    placeholder_text: str = "Ask a question..."
