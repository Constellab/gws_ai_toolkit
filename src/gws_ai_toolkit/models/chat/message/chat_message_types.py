"""Type definitions for chat message unions.

This module defines union types that group related message classes together
for type checking and API contracts.
"""

from gws_ai_toolkit.models.chat.message.chat_message_base import ChatMessageBase
from gws_ai_toolkit.models.chat.message.chat_message_code import ChatMessageCode
from gws_ai_toolkit.models.chat.message.chat_message_dataframe import ChatMessageDataframe
from gws_ai_toolkit.models.chat.message.chat_message_error import ChatMessageError
from gws_ai_toolkit.models.chat.message.chat_message_hint import ChatMessageHint
from gws_ai_toolkit.models.chat.message.chat_message_image import ChatMessageImage
from gws_ai_toolkit.models.chat.message.chat_message_plotly import ChatMessagePlotly
from gws_ai_toolkit.models.chat.message.chat_message_streaming import AssistantStreamingResponse
from gws_ai_toolkit.models.chat.message.chat_message_text import (
    ChatMessageText,
)
from gws_ai_toolkit.models.chat.message.chat_user_message import (
    ChatUserMessageText,
)

# Register all message types in the registry for polymorphic conversion
ChatMessageBase.register_type("text", ChatMessageText)
ChatMessageBase.register_type("user-text", ChatUserMessageText)
ChatMessageBase.register_type("code", ChatMessageCode)
ChatMessageBase.register_type("image", ChatMessageImage)
ChatMessageBase.register_type("plotly", ChatMessagePlotly)
ChatMessageBase.register_type("dataframe", ChatMessageDataframe)
ChatMessageBase.register_type("error", ChatMessageError)
ChatMessageBase.register_type("hint", ChatMessageHint)


# Union of all message types including streaming responses
ChatMessage = (
    ChatMessageText
    | ChatUserMessageText
    | ChatMessageCode
    | ChatMessageImage
    | ChatMessagePlotly
    | ChatMessageDataframe
    | ChatMessageError
    | ChatMessageHint
)

# Union of all message types including streaming responses
AllChatMessages = ChatMessage | AssistantStreamingResponse
