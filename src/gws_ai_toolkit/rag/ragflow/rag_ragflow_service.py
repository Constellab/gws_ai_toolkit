from typing import Any, Generator, List, Optional, Union

from gws_ai_toolkit.rag.common.base_rag_service import BaseRagService
from gws_ai_toolkit.rag.common.rag_models import (RagChatEndStreamResponse,
                                                  RagChatStreamResponse,
                                                  RagChunk, RagDocument)
from gws_core import CredentialsDataOther

from .ragflow_class import (RagFlowChatEndStreamResponse,
                            RagFlowChatStreamResponse, RagFlowChunk,
                            RagFlowDocument, RagFlowUpdateDocumentOptions)
from .ragflow_service import RagFlowService


class RagRagFlowService(BaseRagService):
    """RAG service implementation for RagFlow that uses RagFlowService internally."""

    def __init__(self, route: str, api_key: str):
        super().__init__(route, api_key)
        self._ragflow_service = RagFlowService(route, api_key)

    # Helper methods to convert RagFlow models to Rag models
    def _convert_to_rag_document(self, ragflow_doc: RagFlowDocument) -> RagDocument:
        """Convert RagFlowDocument to RagDocument."""
        return RagDocument(
            id=ragflow_doc.id,
            name=ragflow_doc.name,
            size=ragflow_doc.size,
            parsed_status=ragflow_doc.parsed
        )

    def _convert_to_rag_chunk(self, ragflow_chunk: RagFlowChunk) -> RagChunk:
        """Convert RagFlowChunk to RagChunk."""
        return RagChunk(
            id=ragflow_chunk.id,
            content=ragflow_chunk.content,
            document_id=ragflow_chunk.document_id,
            document_name=ragflow_chunk.document_name,
            score=0.0  # RagFlow chunks don't have scores in this context
        )

    # Implement BaseRagService abstract methods
    def upload_document(self, doc_path: str, dataset_id: str, options: Any,
                        filename: str = None) -> RagDocument:
        """Upload a document to the knowledge base."""
        ragflow_doc = self._ragflow_service.upload_document(doc_path, dataset_id, filename)
        return self._convert_to_rag_document(ragflow_doc)

    def update_document(self, doc_path: str, dataset_id: str, document_id: str,
                        options: Any, filename: str = None) -> RagDocument:
        """Update an existing document in the knowledge base."""
        self.delete_document(dataset_id, document_id)
        return self.upload_document(doc_path, dataset_id, filename)

    def update_document_metadata(self, dataset_id: str, document_id: str,
                                 metadata: dict) -> None:
        options = RagFlowUpdateDocumentOptions(meta_fields=metadata)
        self._ragflow_service.update_document(dataset_id, document_id, options)

    def delete_document(self, dataset_id: str, document_id: str) -> None:
        """Delete a document from the knowledge base."""
        self._ragflow_service.delete_document(dataset_id, document_id)

    def get_all_documents(self, dataset_id: str) -> List[RagDocument]:
        """Get all documents from a knowledge base."""
        ragflow_documents = self._ragflow_service.get_all_documents(dataset_id)
        return [self._convert_to_rag_document(doc) for doc in ragflow_documents]

    def retrieve_chunks(self, dataset_id: str, query: str, top_k: int = 5, **kwargs) -> List[RagChunk]:
        """Retrieve relevant chunks from the knowledge base."""
        response = self._ragflow_service.retrieve_chunks(dataset_id, query, top_k=top_k, **kwargs)
        return [self._convert_to_rag_chunk(chunk) for chunk in response.chunks]

    def chat_stream(self, query: str, conversation_id: str,
                    user: Optional[str] = None,
                    chat_id: Optional[str] = None, **kwargs) -> Generator[
        Union[RagChatStreamResponse, RagChatEndStreamResponse], None, None
    ]:
        """Send a query and get streaming chat response."""
        # RagFlow requires a chat_id, so we need to handle this differently
        # For now, we'll raise NotImplementedError as this needs additional setup
        for response in self.ragflow_service.ask_stream(chat_id, query, conversation_id):
            if isinstance(response, RagFlowChatStreamResponse):
                yield RagChatStreamResponse(answer=response.answer, is_from_beginning=True)
            elif isinstance(response, RagFlowChatEndStreamResponse):
                # Convert sources to RagChunk references
                references = []
                if response.reference:
                    for reference in response.reference:
                        chunk = RagChunk(
                            id=reference.document_id,
                            content=reference.content,
                            document_id=reference.document_id,
                            document_name=reference.document_name
                        )
                        references.append(chunk)

                yield RagChatEndStreamResponse(
                    session_id=response.session_id,
                    sources=references
                )

    @staticmethod
    def from_credentials(credentials: CredentialsDataOther) -> 'RagRagFlowService':
        """Create service instance from credentials."""
        # Check credentials
        if 'route' not in credentials.data:
            raise ValueError("The credentials must contain the field 'route'")
        if 'api_key' not in credentials.data:
            raise ValueError("The credentials must contain the field 'api_key'")
        return RagRagFlowService(credentials.data['route'], credentials.data['api_key'])

    # Provide access to underlying RagFlow service for advanced use cases
    @property
    def ragflow_service(self) -> RagFlowService:
        """Get the underlying RagFlowService instance."""
        return self._ragflow_service
