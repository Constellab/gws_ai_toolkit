

from __future__ import annotations

from typing import List, Optional

from gws_ai_toolkit.models.chat.chat_message_dto import ChatMessageDTO
from gws_ai_toolkit.rag.common.rag_models import RagChatSourceChunk
from gws_core import BaseModelDTO, ModelDTO


class ChatConversationDTO(ModelDTO):
    id: str
    chat_app_id: str
    label: str
    mode: str
    configuration: dict
    external_conversation_id: Optional[str] = None


class SaveChatMessageSourceDTO(BaseModelDTO):
    """DTO for creating a message source."""
    document_id: str
    document_name: str
    score: float
    chunks: list


class SaveChatConversationDTO(BaseModelDTO):
    """DTO for creating a chat conversation."""
    id: Optional[str] = None
    chat_app_name: str
    configuration: dict
    mode: str
    label: Optional[str] = ""
    external_conversation_id: Optional[str] = None
    messages: Optional[List[ChatMessageDTO]] = []
