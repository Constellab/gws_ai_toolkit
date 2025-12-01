from typing import Literal

from gws_ai_toolkit.models.chat.message.chat_message_base import ChatMessageBase


class ChatMessageStreaming(ChatMessageBase):
    """Streaming chat message response from assistant.

    This message type is used during streaming responses from the assistant,
    providing real-time updates as content is generated. It does not extend
    ChatMessageBase as it is not persisted to the database and is only used
    for real-time communication.

    Attributes:
        type: Fixed as "text" to identify this as a text message
        role: Fixed as "assistant" for assistant responses
        content (str): The streaming text content
        external_id (Optional[str]): Optional external system ID

    Example:
        stream_msg = AssistantStreamingResponse(
            content="Here is the beginning of my response...",
            external_id="stream_123"
        )
    """

    type: Literal["streaming-text"] = "streaming-text"
    role: Literal["assistant"] = "assistant"
    content: str
