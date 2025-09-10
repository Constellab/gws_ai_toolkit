from typing import Any, Dict, List, Literal, Optional

from gws_core import BaseModelDTO

RagFlowParserMethod = Literal['naive', 'manual', 'qa', 'table', 'paper', 'book', 'laws', 'resume']


class RagFlowUpdateDocumentOptions(BaseModelDTO):
    display_name: Optional[str] = None
    meta_fields: Optional[Dict[str, Any]] = None


class RagFlowCreateDatasetRequest(BaseModelDTO):
    """Request model for creating a dataset."""
    name: str
    avatar: Optional[str] = None
    description: Optional[str] = None
    language: str = 'English'
    embedding_model: Optional[str] = None
    permission: str = 'me'
    document_count: int = 0
    chunk_count: int = 0
    parse_method: RagFlowParserMethod = 'naive'


class RagFlowUpdateDatasetRequest(BaseModelDTO):
    """Request model for updating a dataset."""
    name: Optional[str] = None
    avatar: Optional[str] = None
    description: Optional[str] = None
    language: Optional[str] = None
    embedding_model: Optional[str] = None
    permission: Optional[str] = None
    parse_method: Optional[RagFlowParserMethod] = None


class RagFlowCreateChatRequest(BaseModelDTO):
    """Request model for creating a chat assistant."""
    name: str
    avatar: Optional[str] = None
    knowledgebases: List[str]
    llm: Dict[str, Any]
    prompt: str


class RagFlowUpdateChatRequest(BaseModelDTO):
    """Request model for updating a chat assistant."""
    name: Optional[str] = None
    avatar: Optional[str] = None
    knowledgebases: Optional[List[str]] = None
    llm: Optional[Dict[str, Any]] = None
    prompt: Optional[str] = None


class RagFlowCreateSessionRequest(BaseModelDTO):
    """Request model for creating a chat session."""
    name: str


class RagflowAskStreamResponse(BaseModelDTO):
    """Response model for streaming chat responses."""
    id: Optional[str]
    content: str
    role: Literal['user', 'assistant']
    reference: List[dict] | None = None
    session_id: str
