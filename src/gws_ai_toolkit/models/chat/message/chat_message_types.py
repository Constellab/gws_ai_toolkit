"""Type definitions for chat message unions.

This module defines union types that group related message classes together
for type checking and API contracts.
"""

from gws_ai_toolkit.models.chat.message.chat_message_code import ChatMessageCode
from gws_ai_toolkit.models.chat.message.chat_message_error import ChatMessageError
from gws_ai_toolkit.models.chat.message.chat_message_hint import ChatMessageHint
from gws_ai_toolkit.models.chat.message.chat_message_image import ChatMessageImage
from gws_ai_toolkit.models.chat.message.chat_message_plotly import (
    ChatMessagePlotly,
    ChatMessagePlotlyFront,
)
from gws_ai_toolkit.models.chat.message.chat_message_source import (
    ChatMessageSource,
    ChatMessageSourceFront,
)
from gws_ai_toolkit.models.chat.message.chat_message_streaming import ChatMessageStreaming
from gws_ai_toolkit.models.chat.message.chat_message_table import (
    ChatMessageTable,
    ChatMessageTableFront,
)
from gws_ai_toolkit.models.chat.message.chat_message_text import (
    ChatMessageText,
)
from gws_ai_toolkit.models.chat.message.chat_user_message import (
    ChatUserMessageText,
)
from gws_ai_toolkit.models.chat.message.chat_user_message_table import (
    ChatUserMessageTable,
    ChatUserMessageTableFront,
)


# Union of all message types including streaming responses
ChatMessage = (
    ChatUserMessageText
    | ChatUserMessageTable
    | ChatMessageText
    | ChatMessageCode
    | ChatMessageImage
    | ChatMessagePlotly
    | ChatMessageTable
    | ChatMessageError
    | ChatMessageHint
    | ChatMessageSource
    | ChatMessageStreaming
)

# Union of all message types including streaming responses
ChatMessageFront = (
    ChatUserMessageText
    | ChatUserMessageTableFront
    | ChatMessageText
    | ChatMessageCode
    | ChatMessageImage
    | ChatMessagePlotlyFront
    | ChatMessageTableFront
    | ChatMessageError
    | ChatMessageHint
    | ChatMessageSourceFront
    | ChatMessageStreaming
)
