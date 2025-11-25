"""Chat message models and types.

This package contains all chat message related classes organized by functionality:
- Base classes for message handling
- Text-based messages (text, error, hint)
- Rich content messages (image, code, plotly, dataframe)
- Streaming responses
- Type unions for API contracts
"""

from gws_ai_toolkit.models.chat.message.chat_message_base import ChatMessageBase
from gws_ai_toolkit.models.chat.message.chat_message_code import ChatMessageCode
from gws_ai_toolkit.models.chat.message.chat_message_dataframe import ChatMessageDataframe
from gws_ai_toolkit.models.chat.message.chat_message_error import (
    ChatMessageError,
)
from gws_ai_toolkit.models.chat.message.chat_message_hint import (
    ChatMessageHint,
)
from gws_ai_toolkit.models.chat.message.chat_message_image import ChatMessageImage
from gws_ai_toolkit.models.chat.message.chat_message_plotly import ChatMessagePlotly
from gws_ai_toolkit.models.chat.message.chat_message_streaming import AssistantStreamingResponse
from gws_ai_toolkit.models.chat.message.chat_message_text import (
    ChatMessageText,
    ChatUserMessageText,
)
from gws_ai_toolkit.models.chat.message.chat_message_types import (
    AllChatMessages,
)

__all__ = [
    # Base
    "ChatMessageBase",
    # Text-based messages
    "ChatMessageText",
    "ChatMessageError",
    "ChatMessageHint",
    "ChatUserMessageText",
    # Rich content messages
    "ChatMessageCode",
    "ChatMessageImage",
    "ChatMessagePlotly",
    "ChatMessageDataframe",
    # Streaming
    "AssistantStreamingResponse",
    # Type unions
    "AllChatMessages",
]
