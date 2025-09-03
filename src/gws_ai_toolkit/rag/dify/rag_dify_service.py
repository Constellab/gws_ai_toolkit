from typing import Any, Generator, List, Optional, Union

from gws_core import CredentialsDataOther, DifyChunkRecord

from gws_ai_toolkit.rag.common.base_rag_service import BaseRagService
from gws_ai_toolkit.rag.common.rag_models import (RagChatEndStreamResponse,
                                                  RagChatStreamResponse,
                                                  RagChunk, RagDocument)

from .dify_class import (DifyDatasetDocument, DifyMetadata,
                         DifySendDocumentOptions,
                         DifySendEndMessageStreamResponse,
                         DifySendMessageStreamResponse,
                         DifyUpdateDocumentOptions,
                         DifyUpdateDocumentsMetadataRequest)
from .dify_service import DifyService


class RagDifyService(BaseRagService):
    """RAG service implementation for Dify that uses DifyService internally."""

    def __init__(self, route: str, api_key: str):
        super().__init__(route, api_key)
        self._dify_service = DifyService(route, api_key)

    # Helper methods to convert Dify models to Rag models
    def _convert_to_rag_document(self, dify_doc: DifyDatasetDocument) -> RagDocument:
        """Convert DifyDatasetDocument to RagDocument."""
        status_mapping = {
            'completed': 'DONE',
            'indexing': 'RUNNING',
            'paused': 'PENDING',
            'error': 'ERROR'
        }
        parsed_status = status_mapping.get(dify_doc.indexing_status, 'PENDING')

        return RagDocument(
            id=dify_doc.id,
            name=dify_doc.name,
            size=dify_doc.tokens,  # Use tokens as size approximation
            parsed_status=parsed_status,
            metadata=dify_doc.meta_fields or {}
        )

    def _convert_to_rag_chunk(self, dify_chunk_record: DifyChunkRecord) -> RagChunk:
        """Convert DifySegment to RagChunk."""
        return RagChunk(
            id=dify_chunk_record.segment.id,
            content=dify_chunk_record.segment.content,
            document_id=dify_chunk_record.segment.document_id,
            document_name=dify_chunk_record.segment.document.name,
            score=dify_chunk_record.score
        )

    # Implement BaseRagService abstract methods
    def upload_document_and_parse(self, doc_path: str, dataset_id: str, options: Any,
                                  filename: str = None) -> RagDocument:
        """Upload a document to the knowledge base."""
        if not isinstance(options, DifySendDocumentOptions):
            raise ValueError("Options must be an instance of DifySendDocumentOptions")
        response = self._dify_service.send_document(doc_path, dataset_id, options, filename)
        return self._convert_to_rag_document(response.document)

    def update_document_and_parse(self, doc_path: str, dataset_id: str, document_id: str,
                                  options: Any, filename: str = None) -> RagDocument:
        """Update an existing document in the knowledge base."""
        if not isinstance(options, DifyUpdateDocumentOptions):
            raise ValueError("Options must be an instance of DifyUpdateDocumentOptions")
        response = self._dify_service.update_document(doc_path, dataset_id, document_id, options, filename)
        return self._convert_to_rag_document(response.document)

    def update_document_metadata(self, dataset_id: str, document_id: str,
                                 metadata: dict) -> None:
        options = DifyUpdateDocumentsMetadataRequest(document_id=document_id, metadata_list=[])

        for key, value in metadata.items():
            # retrieve metadata id from dify
            metadata = self.dify_service.get_or_create_dataset_metadata(dataset_id, key)

            options.metadata_list.append(DifyMetadata(id=metadata.id, value=value, name=key))

        self._dify_service.update_document_metadata(dataset_id, [options])

    def parse_document(self, dataset_id: str, document_id: str) -> RagDocument:
        raise NotImplementedError("Dify does not support re-parsing documents directly.")

    def delete_document(self, dataset_id: str, document_id: str) -> None:
        """Delete a document from the knowledge base."""
        self._dify_service.delete_document(dataset_id, document_id)

    def get_all_documents(self, dataset_id: str) -> List[RagDocument]:
        """Get all documents from a knowledge base."""
        dify_documents = self._dify_service.get_all_documents(dataset_id)
        return [self._convert_to_rag_document(doc) for doc in dify_documents]

    def get_document(self, dataset_id: str, document_id: str) -> Optional[RagDocument]:
        """Get a document from the knowledge base."""
        dify_document = self._dify_service.get_document(dataset_id, document_id)
        if dify_document is None:
            return None
        return self._convert_to_rag_document(dify_document)

    def retrieve_chunks(self, dataset_id: str, query: str, top_k: int = 5,
                        document_ids: List[str] | None = None, **kwargs) -> List[RagChunk]:
        """Retrieve relevant chunks from the knowledge base."""
        if document_ids is not None:
            raise NotImplementedError("Filtering by document_ids is not supported in DifyService.")
        response = self._dify_service.search_chunks(dataset_id, query, top_k=top_k, **kwargs)
        chunks = []
        for record in response.records:
            chunk = self._convert_to_rag_chunk(record)
            chunks.append(chunk)
        return chunks

    def get_document_chunks(self, dataset_id: str, document_id: str, keyword: str | None = None,
                            page: int = 1, limit: int = 20) -> List[RagChunk]:
        response = self._dify_service.get_document_chunks(dataset_id, document_id, keyword, page, limit)
        return [self._convert_to_rag_chunk(chunk) for chunk in response]

    def chat_stream(self, query: str, conversation_id: Optional[str] = None,
                    user: Optional[str] = None, chat_id: Optional[str] = None, **kwargs) -> Generator[
        Union[RagChatStreamResponse, RagChatEndStreamResponse], None, None
    ]:
        """Send a query and get streaming chat response."""
        for response in self._dify_service.send_message_stream(query, user, conversation_id, **kwargs):
            if isinstance(response, DifySendMessageStreamResponse):
                yield RagChatStreamResponse(answer=response.answer, is_from_beginning=False)
            elif isinstance(response, DifySendEndMessageStreamResponse):
                # Convert sources to RagChunk references
                chat_end = RagChatEndStreamResponse(session_id=response.conversation_id)
                if response.sources:
                    for source in response.sources:
                        chat_end.add_source(
                            document_id=source.document_id,
                            document_name=source.document_name,
                            chunk_id='',
                            chunk_score=source.score,
                            chunk_content=None
                        )

                yield chat_end

    @staticmethod
    def from_credentials(credentials: CredentialsDataOther) -> 'RagDifyService':
        """Create service instance from credentials."""
        # Check credentials
        if 'route' not in credentials.data:
            raise ValueError("The credentials must contain the field 'route'")
        if 'api_key' not in credentials.data:
            raise ValueError("The credentials must contain the field 'api_key'")
        return RagDifyService(credentials.data['route'], credentials.data['api_key'])

    # Provide access to underlying Dify service for advanced use cases
    @property
    def dify_service(self) -> DifyService:
        """Get the underlying DifyService instance."""
        return self._dify_service
