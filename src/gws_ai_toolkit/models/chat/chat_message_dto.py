import uuid
from typing import List, Literal, Optional

import plotly.graph_objects as go
from gws_ai_toolkit.rag.common.rag_models import RagChatSource
from gws_core import BaseModelDTO
from PIL import Image


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
    id: Optional[str] = None
    role: Literal['user', 'assistant']
    external_id: Optional[str] = None
    sources: Optional[List[RagChatSource]] = []

    def is_user_message(self) -> bool:
        """Check if this message was sent by the user.

        Returns:
            bool: True if message role is 'user', False if 'assistant'
        """
        return self.role == "user"


class ChatMessageText(ChatMessageBase):
    """Chat message containing text content.

    Specialized chat message for text-based content, ensuring proper typing
    and validation for text messages. This is the most common message type
    in chat conversations.

    Attributes:
        type: Fixed as "text" to identify this as a text message
        content (str): The text content of the message

    Example:
        text_msg = ChatMessageText(
            role="user",
            content="What is the weather today?",
            id="msg_text_123"
        )
    """
    type: Literal["text"] = "text"
    content: str


class ChatMessageImage(ChatMessageBase):
    """ Object
    """
    type: Literal["image"] = "image"

    image: Image.Image | None

    class Config:
        arbitrary_types_allowed = True


class ChatMessageCode(ChatMessageBase):
    """Chat message containing code content.

    Specialized chat message for code blocks, providing proper formatting
    and syntax highlighting for programming code shared in conversations.
    Commonly used for code examples, generated scripts, or code analysis.

    Attributes:
        type: Fixed as "code" to identify this as a code message
        content (str): The code content with proper formatting

    Example:
        code_msg = ChatMessageCode(
            role="assistant",
            code="print('Hello, world!')",
            id="msg_code_123"
        )
    """
    type: Literal["code"] = "code"
    code: str


class ChatMessagePlotly(ChatMessageBase):
    """Chat message containing Plotly figure content.

    Specialized chat message for interactive Plotly visualizations created
    through function calls. Used to display charts, graphs, and data
    visualizations in the chat interface.

    Attributes:
        type: Fixed as "plotly" to identify this as a plotly message
        figure: The Plotly figure object for rendering

    Example:
        plotly_msg = ChatMessagePlotly(
            role="assistant",
            id="msg_plotly_123",
            figure=go.Figure(data=[go.Bar(x=['A', 'B'], y=[1, 2])])
        )
    """
    type: Literal["plotly"] = "plotly"
    figure: go.Figure | None

    class Config:
        arbitrary_types_allowed = True


class ChatMessageError(ChatMessageBase):
    """Chat message representing an error.

    Specialized chat message for conveying error information within the
    chat conversation. Used to inform users about issues or problems
    encountered during interactions.

    Attributes:
        type: Fixed as "error" to identify this as an error message
        content (str): The error message content

    Example:
        error_msg = ChatMessageError(
            role="assistant",
            content="An error occurred while processing your request.",
            id="msg_error_123"
        )
    """
    type: Literal["error"] = "error"
    error: str


class ChatMessageHint(ChatMessageBase):
    """Chat message containing hint content.

    Specialized chat message for providing hints, tips, or helpful suggestions
    to users during their chat conversation. Used to offer guidance or provide
    contextual information without being a direct response.

    Attributes:
        type: Fixed as "hint" to identify this as a hint message
        content (str): The hint message content

    Example:
        hint_msg = ChatMessageHint(
            role="assistant",
            content="Try asking about specific topics for better results.",
            id="msg_hint_123"
        )
    """
    type: Literal["hint"] = "hint"
    content: str


# Type used  for front-end rendering
ChatMessageDTO = ChatMessageText | ChatMessageCode | ChatMessageImage | ChatMessagePlotly | ChatMessageError | ChatMessageHint
