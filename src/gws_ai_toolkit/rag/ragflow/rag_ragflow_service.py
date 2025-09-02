from typing import Any, Generator, List, Literal, Optional, Union

from gws_core import CredentialsDataOther
from ragflow_sdk import Chunk, Document

from gws_ai_toolkit.rag.common.base_rag_service import BaseRagService
from gws_ai_toolkit.rag.common.rag_models import (RagChatEndStreamResponse,
                                                  RagChatStreamResponse,
                                                  RagChunk, RagDocument)

from .ragflow_class import RagFlowUpdateDocumentOptions
from .ragflow_service import RagFlowService


class RagRagFlowService(BaseRagService):
    """RAG service implementation for RagFlow that uses RagFlowService internally."""

    def __init__(self, route: str, api_key: str):
        super().__init__(route, api_key)
        self._ragflow_service = RagFlowService(route, api_key)

    # Implement BaseRagService abstract methods
    def upload_document_and_parse(self, doc_path: str, dataset_id: str, options: Any,
                                  filename: str = None) -> RagDocument:
        """Upload a document to the knowledge base."""
        sdk_doc = self._ragflow_service.upload_document(doc_path, dataset_id, filename)
        self._ragflow_service.parse_documents(dataset_id, [sdk_doc.id])
        return self._convert_document_to_rag_document(sdk_doc)

    def update_document_and_parse(self, doc_path: str, dataset_id: str, document_id: str,
                                  options: Any, filename: str = None) -> RagDocument:
        """Update an existing document in the knowledge base."""
        self.delete_document(dataset_id, document_id)
        return self.upload_document_and_parse(doc_path, dataset_id, filename)

    def update_document_metadata(self, dataset_id: str, document_id: str,
                                 metadata: dict) -> None:
        options = RagFlowUpdateDocumentOptions(meta_fields=metadata)
        self._ragflow_service.update_document(dataset_id, document_id, options)

    def parse_document(self, dataset_id: str, document_id: str) -> RagDocument:
        self._ragflow_service.parse_documents(dataset_id, [document_id])
        return self.get_document(dataset_id, document_id)

    def delete_document(self, dataset_id: str, document_id: str) -> None:
        """Delete a document from the knowledge base."""
        self._ragflow_service.delete_document(dataset_id, document_id)

    def get_all_documents(self, dataset_id: str) -> List[RagDocument]:
        """Get all documents from a knowledge base."""
        sdk_documents = self._ragflow_service.get_all_documents(dataset_id)
        return [self._convert_document_to_rag_document(doc) for doc in sdk_documents]

    def get_document(self, dataset_id: str, document_id: str) -> Optional[RagDocument]:
        """Get a document from the knowledge base."""
        try:
            sdk_document = self._ragflow_service.get_document(dataset_id, document_id)
            return self._convert_document_to_rag_document(sdk_document)
        except ValueError:
            return None

    def retrieve_chunks(self, dataset_id: str, query: str, top_k: int = 5,
                        document_ids: List[str] | None = None,
                        **kwargs) -> List[RagChunk]:
        """Retrieve relevant chunks from the knowledge base."""
        sdk_response = self._ragflow_service.retrieve_chunks(
            dataset_id, query, top_k=top_k, document_ids=document_ids, **kwargs)

        # Convert SDK response directly to RagChunk
        chunks = []
        for chunk in sdk_response:
            rag_chunk = self._convert_chunk_to_rag_chunk(chunk)
            chunks.append(rag_chunk)

        return chunks

    def get_document_chunks(self, dataset_id: str, document_id: str, keyword: str | None = None,
                            page: int = 1, limit: int = 20) -> List[RagChunk]:
        response = self._ragflow_service.get_document_chunks(dataset_id, document_id, keyword, page, limit)
        return [self._convert_chunk_to_rag_chunk(chunk) for chunk in response]

    def chat_stream(self,
                    query: str,
                    conversation_id: Optional[str] = None,
                    user: Optional[str] = None,
                    chat_id: Optional[str] = None,
                    **kwargs) -> Generator[
        Union[RagChatStreamResponse, RagChatEndStreamResponse], None, None
    ]:
        """Send a query and get streaming chat response."""
        # RagFlow requires a chat_id, so we need to handle this differently
        for answer in self._ragflow_service.ask_stream(chat_id, query, conversation_id):
            if answer.role == 'assistant':
                if answer.reference:
                    # Convert directly to RagChunk references
                    rag_references = []
                    for ref in answer.reference:
                        chunk = RagChunk(
                            id=ref['id'],
                            content=ref['content'],
                            document_id=ref['document_id'],
                            document_name=ref['document_name'],
                            score=ref['vector_similarity']
                        )
                        rag_references.append(chunk)

                    yield RagChatEndStreamResponse(
                        session_id=answer.session_id,
                        sources=rag_references
                    )
                else:
                    yield RagChatStreamResponse(answer=answer.content, is_from_beginning=True)

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

    ################################### CONVERTERS #####################################

    # Helper methods to convert RagFlow models to Rag models
    def _convert_document_to_rag_document(self, document: Document) -> RagDocument:
        """Convert SDK Document directly to RagDocument."""

        parsed_status: Literal['DONE', 'PENDING', 'RUNNING', 'ERROR'] = None
        if document.run == 'UNSTART':
            parsed_status = 'PENDING'
        elif document.run == 'DONE':
            parsed_status = 'DONE'
        elif document.run == 'RUNNING':
            parsed_status = 'RUNNING'
        else:  # FAIL
            parsed_status = 'ERROR'

        return RagDocument(
            id=document.id,
            name=document.name,
            size=document.size,
            parsed_status=parsed_status
        )

    def _convert_chunk_to_rag_chunk(self, chunk: Chunk) -> RagChunk:
        """Convert SDK chunk data directly to RagChunk."""
        return RagChunk(
            id=chunk.id,
            content=chunk.content,
            document_id=chunk.document_id,
            document_name=chunk.document_name,
            score=chunk.vector_similarity
        )
