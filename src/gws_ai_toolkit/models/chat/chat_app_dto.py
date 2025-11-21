

from datetime import datetime

from gws_core import BaseModelDTO, ModelDTO


class SaveChatAppDTO(BaseModelDTO):
    """DTO for creating or updating a ChatApp."""
    name: str


class ChatAppDTO(ModelDTO):
    """DTO for displaying ChatApp information."""
    name: str
