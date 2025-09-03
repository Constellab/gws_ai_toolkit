from typing import Any, List, Literal, Optional

from gws_core import BaseModelDTO
from PIL import Image

from gws_ai_toolkit.rag.common.rag_models import RagChatSource


class ChatMessage(BaseModelDTO):
    role: Literal['user', 'assistant']
    type: Literal["text", "image", "code"]
    content: Any
    id: str
    sources: Optional[List[RagChatSource]] = []
    data: Optional[Image.Image] = None  # For image messages

    class Config:
        arbitrary_types_allowed = True

    def is_user_message(self) -> bool:
        return self.role == "user"


class ChatMessageText(ChatMessage):
    type: Literal["text"] = "text"
    content: str


class ChatMessageImage(ChatMessage):
    type: Literal["image"] = "image"


class ChatMessageCode(ChatMessage):
    type: Literal["code"] = "code"
    content: str
