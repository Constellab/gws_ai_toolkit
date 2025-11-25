from typing import Literal

from gws_core import BaseModelDTO


class ChatMessageBase(BaseModelDTO):
    """Base chat message class for all message types in the chat system.

    This class serves as the foundation for all chat messages, providing common
    attributes and functionality shared across different message types (text,
    image, code). It integrates with the RAG system to support source citations
    and handles various content types.

    Attributes:
        role (Literal['user', 'assistant']): Message sender - either user or AI assistant
        type (Literal["text", "image", "code"]): Content type for proper rendering
        content (Any): Message content - varies by message type
        id (str): Unique identifier for the message
        external_id (Optional[str]): Optional external system ID (from openai, dify, ragflow...) for the message
        sources (Optional[List[RagChatSource]]): Source citations for RAG responses

    Features:
        - Flexible content handling for different message types
        - Source citation support for RAG-enhanced responses
        - Role-based message identification
        - Unique message identification
        - File path support for image content

    Example:
        message = ChatMessage(
            role="assistant",
            type="text",
            content="Hello, how can I help?",
            id="msg_123",
            sources=[source1, source2]
        )
    """

    type: str
    role: Literal["user", "assistant"]
    external_id: str | None = None
