from typing import List, Literal, Optional

from gws_core import BaseModelDTO

from gws_ai_toolkit.rag.common.rag_models import RagChunk


class ChatMessage(BaseModelDTO):
    role: Literal['user', 'assistant']
    content: str
    id: str
    sources: Optional[List[RagChunk]] = []
