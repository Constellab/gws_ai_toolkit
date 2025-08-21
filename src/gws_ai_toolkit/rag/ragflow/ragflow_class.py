from typing import Any, Dict, List, Literal, Optional

from gws_core import BaseModelDTO

RagFlowChunkMethod = Literal['naive', 'manual', 'qa', 'table', 'paper', 'book', 'laws', 'resume']
RagFlowParserMethod = Literal['naive', 'manual', 'qa', 'table', 'paper', 'book', 'laws', 'resume']


class RagFlowDocument(BaseModelDTO):
    """Model for document information in the response."""
    id: str
    name: str
    size: Optional[int] = None
    knowledgebase_id: str
    type: str
    parsed: Literal['DONE', 'PENDING', 'RUNNING', 'ERROR']


class RagFlowSendDocumentResponse(BaseModelDTO):
    """Model for the response from sending a document."""
    code: int
    message: str
    data: List[RagFlowDocument]

class RagFlowUpdateDocumentOptions(BaseModelDTO):
    display_name: Optional[str] = None
    meta_fields: Optional[Dict[str, Any]] = None


class RagFlowDataset(BaseModelDTO):
    """Model for dataset/knowledgebase information."""
    avatar: Optional[str] = None
    chunk_count: int
    created_by: str
    description: Optional[str] = None
    document_count: int
    embedding_model: str
    id: str
    language: str
    name: str
    parse_method: str
    permission: str
    tenant_id: str
    updated_at: str
    created_at: str


class RagFlowListDatasetsResponse(BaseModelDTO):
    """Model for the response from retrieving datasets."""
    code: int
    message: str
    data: List[RagFlowDataset]


class RagFlowListDocumentsResponse(BaseModelDTO):
    """Model for the response from retrieving documents."""
    code: int
    message: str
    data: List[RagFlowDocument]


class RagFlowChunk(BaseModelDTO):
    """Model for chunk/segment information."""
    id: str
    content: str
    document_id: str
    document_name: str
    dataset_id: str


class RagFlowRetrieveResponse(BaseModelDTO):
    """Model for the response from chunk retrieval."""
    code: int
    message: str
    data: Dict[str, Any]
    chunks: List[RagFlowChunk]


class RagFlowChatMessage(BaseModelDTO):
    """Model for chat message response."""
    role: Literal['user', 'assistant']
    content: str
    reference: Optional[List[RagFlowChunk]] = None


class RagFlowChatStreamResponse(BaseModelDTO):
    """Model for streaming chat response."""
    answer: str
    reference: Optional[List[RagFlowChunk]] = None


class RagFlowChatEndStreamResponse(BaseModelDTO):
    """Model for end of chat stream response."""
    session_id: str
    message_id: str
    reference: Optional[List[RagFlowChunk]] = None


class RagFlowSession(BaseModelDTO):
    """Model for chat session."""
    id: str
    name: str
    messages: List[RagFlowChatMessage]
    chat_id: str
    created_at: str
    updated_at: str


class RagFlowListSessionsResponse(BaseModelDTO):
    """Model for the response from retrieving sessions."""
    code: int
    message: str
    data: List[RagFlowSession]


class RagFlowChat(BaseModelDTO):
    """Model for chat assistant."""
    id: str
    name: str
    avatar: Optional[str] = None
    knowledgebases: List[str]
    llm: Dict[str, Any]
    prompt: str
    created_by: str
    updated_at: str
    created_at: str


class RagFlowListChatsResponse(BaseModelDTO):
    """Model for the response from retrieving chats."""
    code: int
    message: str
    data: List[RagFlowChat]


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

