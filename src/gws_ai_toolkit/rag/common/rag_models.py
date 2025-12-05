
from gws_core import BaseModelDTO

from .rag_enums import RagDocumentStatus


class RagDocument(BaseModelDTO):
    """Base class for documents across RAG implementations."""

    id: str
    name: str
    size: int | None = None
    parsed_status: RagDocumentStatus


class RagChunk(BaseModelDTO):
    """Base class for document chunks/segments."""

    id: str
    content: str | None
    document_id: str
    document_name: str
    score: float


class RagChatStreamResponse(BaseModelDTO):
    """Base class for streaming chat responses."""

    id: str | None
    answer: str
    # If true, the response is from the beginning of the conversation (should not concatenate)
    # If false, the response is a continuation of the previous messages
    is_from_beginning: bool
    session_id: str


class RagChatSourceChunk(BaseModelDTO):
    chunk_id: str
    content: str | None = None
    score: float


class RagChatSource(BaseModelDTO):
    document_id: str
    document_name: str
    score: float = 0
    chunks: list[RagChatSourceChunk] = []

    def __init__(self, **data):
        super().__init__(**data)
        if self.chunks:
            self.score = max(chunk.score for chunk in self.chunks)

    def add_chunk(self, chunk: RagChatSourceChunk) -> None:
        self.chunks.append(chunk)
        self.score = max(self.score, chunk.score)


class RagChatEndStreamResponse(BaseModelDTO):
    """Base class for end-of-stream chat responses."""

    session_id: str
    sources: list[RagChatSource] = []

    def add_source(
        self,
        document_id: str,
        document_name: str,
        chunk_id: str,
        chunk_score: float,
        chunk_content: str | None,
    ) -> None:
        chat_source = self.get_source_by_document_id(document_id)
        if not chat_source:
            chat_source = RagChatSource(document_id=document_id, document_name=document_name)
            self.sources.append(chat_source)

        chat_source.add_chunk(
            RagChatSourceChunk(chunk_id=chunk_id, content=chunk_content, score=chunk_score)
        )

    def get_source_by_document_id(self, document_id: str) -> RagChatSource | None:
        for source in self.sources:
            if source.document_id == document_id:
                return source
        return None


class RagCredentials(BaseModelDTO):
    """Base class for RAG service credentials."""

    route: str
    api_key: str
