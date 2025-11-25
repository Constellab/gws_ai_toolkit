from __future__ import annotations

from gws_core import BaseModelDTO, ModelDTO

from gws_ai_toolkit.models.chat.message import ChatMessageBase
from gws_ai_toolkit.models.chat.message.chat_message_text import ChatUserMessageText


class ChatConversationDTO(ModelDTO):
    id: str
    chat_app_id: str
    label: str
    mode: str
    configuration: dict
    external_conversation_id: str | None = None


class SaveChatMessageSourceDTO(BaseModelDTO):
    """DTO for creating a message source."""

    document_id: str
    document_name: str
    score: float
    chunks: list


class SaveChatConversationDTO(BaseModelDTO):
    """DTO for creating a chat conversation."""

    id: str | None = None
    chat_app_name: str
    configuration: dict
    mode: str
    label: str | None = ""
    external_conversation_id: str | None = None
    messages: list[ChatMessageBase] | None = []

    def get_default_label(self) -> str:
        if self.messages and len(self.messages) > 0:
            users_message = [msg for msg in self.messages if isinstance(msg, ChatUserMessageText)]
            if users_message and len(users_message) > 0:
                first_message = users_message[0]
                label = first_message.content[:60]
                if label:
                    return label

        return "New Conversation"
