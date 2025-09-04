from typing import Any, List, Literal, Optional

from gws_core import BaseModelDTO
from PIL import Image

from gws_ai_toolkit.rag.common.rag_models import RagChatSource


class ChatMessage(BaseModelDTO):
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
        sources (Optional[List[RagChatSource]]): Source citations for RAG responses
        data (Optional[Image.Image]): PIL Image data for image messages
        
    Features:
        - Flexible content handling for different message types
        - Source citation support for RAG-enhanced responses
        - Role-based message identification
        - Unique message identification
        - PIL Image integration for visual content
        
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
    type: Literal["text", "image", "code"]
    content: Any
    id: str
    sources: Optional[List[RagChatSource]] = []
    data: Optional[Image.Image] = None  # For image messages

    class Config:
        arbitrary_types_allowed = True

    def is_user_message(self) -> bool:
        """Check if this message was sent by the user.
        
        Returns:
            bool: True if message role is 'user', False if 'assistant'
        """
        return self.role == "user"


class ChatMessageText(ChatMessage):
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


class ChatMessageImage(ChatMessage):
    """Chat message containing image content.
    
    Specialized chat message for image content, supporting PIL Image objects
    for display in the chat interface. Used for AI-generated images or
    image analysis responses.
    
    Attributes:
        type: Fixed as "image" to identify this as an image message
        data: PIL Image object stored in the parent class data field
        
    Example:
        image_msg = ChatMessageImage(
            role="assistant",
            content="Generated chart",
            id="msg_img_123",
            data=pil_image_object
        )
    """
    type: Literal["image"] = "image"


class ChatMessageCode(ChatMessage):
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
    content: str
