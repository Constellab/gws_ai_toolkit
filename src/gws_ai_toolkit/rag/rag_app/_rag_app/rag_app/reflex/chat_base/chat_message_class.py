import json
from typing import List, Literal, Optional

import plotly.graph_objects as go
from gws_core import BaseModelDTO
from PIL import Image
from pydantic import field_validator

from gws_ai_toolkit.rag.common.rag_models import RagChatSource


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
    role: Literal['user', 'assistant']
    id: str
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
    """Chat message containing image content.

    Specialized chat message for image content, using full image paths
    for display in the chat interface. Used for AI-generated images or
    image analysis responses.

    Attributes:
        type: Fixed as "image" to identify this as an image message
        image_name: Full path to the image file (stored in history images folder)
        content: Optional text description/caption for the image

    Example:
        image_msg = ChatMessageImage(
            role="assistant",
            content="Generated chart",
            id="msg_img_123",
            image_name="/path/to/history/images/image_123.png"
        )
    """
    type: Literal["image"] = "image"
    filename: str


class ChatMessageImageFront(ChatMessageBase):
    """ Object
    """
    type: Literal["image"] = "image"

    image: Image.Image

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
            content="print('Hello, world!')",
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
        filename: The filename where the Plotly figure is stored

    Example:
        plotly_msg = ChatMessagePlotly(
            role="assistant",
            id="msg_plotly_123",
            figure=go.Figure(data=[go.Bar(x=['A', 'B'], y=[1, 2])])
        )
    """
    type: Literal["plotly"] = "plotly"
    filename: str


class ChatMessagePlotlyFront(ChatMessageBase):
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
    figure: go.Figure

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


# Type used for the storage and internal processing
ChatMessage = ChatMessageText | ChatMessageCode | ChatMessageImage | ChatMessagePlotly | ChatMessageError

# Type used  for front-end rendering
ChatMessageFront = ChatMessageText | ChatMessageCode | ChatMessageImageFront | ChatMessagePlotlyFront | ChatMessageError
