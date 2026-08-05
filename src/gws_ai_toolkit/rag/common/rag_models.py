from gws_core import BaseModelDTO


class RagChatSourceChunk(BaseModelDTO):
    chunk_id: str
    content: str | None = None
    score: float


class RagChatSource(BaseModelDTO):
    id: str
    document_id: str
    document_name: str
    score: float = 0
    chunk: RagChatSourceChunk | None = None
