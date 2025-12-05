from typing import Any, Literal

from gws_core import BaseModelDTO

RagFlowParserMethod = Literal["naive", "manual", "qa", "table", "paper", "book", "laws", "resume"]


class RagFlowUpdateDocumentOptions(BaseModelDTO):
    display_name: str | None = None
    meta_fields: dict[str, Any] | None = None


class RagFlowCreateDatasetRequest(BaseModelDTO):
    """Request model for creating a dataset."""

    name: str
    avatar: str | None = None
    description: str | None = None
    language: str = "English"
    embedding_model: str | None = None
    permission: str = "me"
    document_count: int = 0
    chunk_count: int = 0
    parse_method: RagFlowParserMethod = "naive"


class RagFlowUpdateDatasetRequest(BaseModelDTO):
    """Request model for updating a dataset."""

    name: str | None = None
    avatar: str | None = None
    description: str | None = None
    language: str | None = None
    embedding_model: str | None = None
    permission: str | None = None
    parse_method: RagFlowParserMethod | None = None


class RagFlowCreateChatRequest(BaseModelDTO):
    """Request model for creating a chat assistant."""

    name: str
    avatar: str | None = ""
    knowledgebases: list[str] | None = []
    llm: dict[str, Any] | None = None
    prompt: dict[str, Any] | None = None


class RagFlowUpdateChatRequest(BaseModelDTO):
    """Request model for updating a chat assistant."""

    name: str | None = None
    avatar: str | None = None
    knowledgebases: list[str] | None = None
    llm: dict[str, Any] | None = None
    prompt: str | None = None


class RagFlowCreateSessionRequest(BaseModelDTO):
    """Request model for creating a chat session."""

    name: str


class RagflowAskStreamResponse(BaseModelDTO):
    """Response model for streaming chat responses.
    Note: there is no id in the SDK response for answers."""

    content: str
    role: Literal["user", "assistant"]
    reference: list[dict] | None = None
    session_id: str
