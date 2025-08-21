from typing import List, Optional

from gws_core import BaseModelDTO

from .rag_enums import RagDocumentStatus


class RagDocument(BaseModelDTO):
    """Base class for documents across RAG implementations."""
    id: str
    name: str
    size: Optional[int] = None
    parsed_status: RagDocumentStatus


class RagChunk(BaseModelDTO):
    """Base class for document chunks/segments."""
    id: str
    content: Optional[str]
    document_id: str
    document_name: str
    score: float


class RagChatStreamResponse(BaseModelDTO):
    """Base class for streaming chat responses."""
    answer: str
    # If true, the response is from the beginning of the conversation (should not concatenate)
    # If false, the response is a continuation of the previous messages
    is_from_beginning: bool


class RagChatEndStreamResponse(BaseModelDTO):
    """Base class for end-of-stream chat responses."""
    session_id: str = None
    sources: List[RagChunk] = None


class RagCredentials(BaseModelDTO):
    """Base class for RAG service credentials."""
    route: str
    api_key: str
