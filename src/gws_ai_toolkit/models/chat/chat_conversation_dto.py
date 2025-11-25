from __future__ import annotations

from gws_core import BaseModelDTO, ModelDTO

from gws_ai_toolkit.models.chat.message import ChatMessageBase


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
