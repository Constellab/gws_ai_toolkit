from abc import ABC, abstractmethod
from collections.abc import Generator
from typing import Any

from gws_core import CredentialsDataOther

from .rag_models import RagChatEndStreamResponse, RagChatStreamResponse, RagChunk, RagDocument


class BaseRagService(ABC):
    """Abstract base class for RAG services (Dify, RagFlow, etc.)."""

    route: str
    api_key: str

    def __init__(self, route: str, api_key: str):
        self.route = route
        self.api_key = api_key

    # Document Management
    @abstractmethod
    def upload_document_and_parse(
        self, doc_path: str, dataset_id: str, options: Any, filename: str = None
    ) -> RagDocument:
        """Upload a document to the knowledge base."""
        raise NotImplementedError

    @abstractmethod
    def update_document_and_parse(
        self, doc_path: str, dataset_id: str, document_id: str, options: Any, filename: str = None
    ) -> RagDocument:
        """Update an existing document in the knowledge base."""
        raise NotImplementedError

    @abstractmethod
    def update_document_metadata(self, dataset_id: str, document_id: str, metadata: dict) -> None:
        """Update metadata fields of an existing document in the knowledge base."""
        raise NotImplementedError

    @abstractmethod
    def parse_document(self, dataset_id: str, document_id: str) -> RagDocument:
        """Parse a document in the knowledge base."""
        raise NotImplementedError

    @abstractmethod
    def delete_document(self, dataset_id: str, document_id: str) -> None:
        """Delete a document from the knowledge base."""
        raise NotImplementedError

    @abstractmethod
    def get_all_documents(self, dataset_id: str) -> list[RagDocument]:
        """Get all documents from a knowledge base."""
        raise NotImplementedError

    @abstractmethod
    def get_document(self, dataset_id: str, document_id: str) -> RagDocument | None:
        """Get a document from the knowledge base."""
        raise NotImplementedError

    # Chunk Retrieval
    @abstractmethod
    def retrieve_chunks(
        self,
        dataset_id: str,
        query: str,
        top_k: int = 5,
        document_ids: list[str] | None = None,
        **kwargs,
    ) -> list[RagChunk]:
        """Retrieve relevant chunks from the knowledge base."""
        raise NotImplementedError

    # Document Chunk Retrieval
    @abstractmethod
    def get_document_chunks(
        self,
        dataset_id: str,
        document_id: str,
        keyword: str | None = None,
        page: int = 1,
        limit: int = 20,
    ) -> list[RagChunk]:
        """Get chunks for a specific document using SDK."""
        raise NotImplementedError

    # Chat/Q&A
    @abstractmethod
    def chat_stream(
        self,
        query: str,
        conversation_id: str | None = None,
        user_id: str | None = None,
        chat_id: str | None = None,
        **kwargs,
    ) -> Generator[RagChatStreamResponse | RagChatEndStreamResponse, None, None]:
        """Send a query and get streaming chat response."""
        raise NotImplementedError

    # Factory method
    @staticmethod
    @abstractmethod
    def from_credentials(credentials: CredentialsDataOther) -> "BaseRagService":
        """Create service instance from credentials."""
        raise NotImplementedError

    # Common utility methods
    def get_base_url(self) -> str:
        """Get the base URL of the RAG service."""
        return self.route.split("/")[0] + "//" + self.route.split("/")[2]
