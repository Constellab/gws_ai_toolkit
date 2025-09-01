from typing import Any, Generator, List, Optional

from gws_core import CredentialsDataOther
from ragflow_sdk import Chat, Chunk, DataSet, Document, RAGFlow, Session

from gws_ai_toolkit.rag.ragflow.ragflow_class import (
    RagFlowCreateChatRequest, RagFlowCreateDatasetRequest,
    RagFlowCreateSessionRequest, RagFlowUpdateChatRequest,
    RagFlowUpdateDatasetRequest, RagFlowUpdateDocumentOptions)


class RagFlowService:
    """Service to interact with RagFlow using the Python SDK"""

    _client: RAGFlow  # RagFlow client instance
    base_url: str
    api_key: str

    def __init__(self, base_url: str, api_key: str):
        self.base_url = base_url.rstrip('/')
        self.api_key = api_key
        self._client = None

    def _get_client(self):
        """Get or create the RagFlow SDK client."""
        if self._client is None:
            try:

                self._client = RAGFlow(api_key=self.api_key, base_url=self.base_url)
            except ImportError:
                raise RuntimeError(
                    "RagFlow SDK is not installed. Please install it with: pip install ragflow-sdk"
                )
        return self._client

    ################################# DATASET MANAGEMENT #################################

    def create_dataset(self, dataset: RagFlowCreateDatasetRequest) -> DataSet:
        """Create a new dataset/knowledgebase using SDK.

        Parameters
        ----------
        dataset : RagFlowCreateDatasetRequest
            Dataset configuration

        Returns
        -------
        DataSet
            Created dataset information from SDK
        """
        client = self._get_client()

        try:
            sdk_dataset = client.create_dataset(
                name=dataset.name,
                chunk_method=dataset.parse_method if hasattr(dataset, 'parse_method') else 'naive',
                permission=dataset.permission if hasattr(dataset, 'permission') else 'me'
            )

            return sdk_dataset
        except Exception as e:
            raise RuntimeError(f"Error creating dataset: {str(e)}") from e

    def get_dataset(self, dataset_id: str) -> DataSet:
        """Get a single dataset by ID using list_datasets."""
        client = self._get_client()
        dk_datasets = client.list_datasets(id=dataset_id)

        if len(dk_datasets) == 0:
            raise ValueError(f"Dataset {dataset_id} not found")

        return dk_datasets[0]

    def list_datasets(self, page: int = 1, page_size: int = 10) -> List[DataSet]:
        """List all datasets/knowledgebases using SDK."""
        client = self._get_client()

        try:
            sdk_datasets = client.list_datasets()

            # Apply pagination
            start_idx = (page - 1) * page_size
            end_idx = start_idx + page_size

            return sdk_datasets[start_idx:end_idx]
        except Exception as e:
            raise RuntimeError(f"Error listing datasets: {str(e)}") from e

    def update_dataset(self, dataset_id: str, updates: RagFlowUpdateDatasetRequest) -> DataSet:
        """Update a dataset (limited support in SDK)."""
        # Note: SDK may have limited update support, this is a placeholder
        raise NotImplementedError("Dataset updates not fully supported in SDK")

    def delete_datasets(self, dataset_ids: List[str]) -> None:
        """Delete multiple datasets using SDK."""
        client = self._get_client()

        try:
            client.delete_datasets(ids=dataset_ids)
        except Exception as e:
            raise RuntimeError(f"Error deleting datasets: {str(e)}") from e

    ################################# DOCUMENT MANAGEMENT #################################

    def upload_documents(self, doc_paths: List[str], dataset_id: str,
                         filenames: List[str] = None) -> List[Document]:
        """Upload multiple documents using SDK."""
        try:
            # Get dataset object using our helper method
            dataset = self.get_dataset(dataset_id)

            # Prepare documents for upload
            documents = []
            for i, doc_path in enumerate(doc_paths):
                filename = filenames[i] if filenames and i < len(filenames) else None
                display_name = filename if filename else doc_path.split('/')[-1]

                with open(doc_path, 'rb') as f:
                    documents.append({
                        'display_name': display_name,
                        'blob': f.read()
                    })

            # Upload documents
            ragflow_response: List[Document] = dataset.upload_documents(documents)
            return ragflow_response

        except Exception as e:
            raise RuntimeError(f"Error uploading documents: {str(e)}") from e

    def upload_document(self, doc_paths: str, dataset_id: str,
                        filename: str = None) -> Document:
        """Upload single document using SDK."""
        response = self.upload_documents([doc_paths], dataset_id, [filename] if filename else None)
        return response[0]

    def list_documents(self, dataset_id: str, page: int = 1, page_size: int = 10) -> List[Document]:
        """List documents using SDK."""
        try:
            # Get dataset object using our helper method
            dataset = self.get_dataset(dataset_id)

            # List documents
            sdk_documents = dataset.list_documents()

            # Apply pagination
            start_idx = (page - 1) * page_size
            end_idx = start_idx + page_size

            return sdk_documents[start_idx:end_idx]

        except Exception as e:
            raise RuntimeError(f"Error listing documents: {str(e)}") from e

    def get_all_documents(self, dataset_id: str) -> List[Document]:
        """Get all documents using SDK."""

        try:
            # Get dataset object using our helper method
            dataset = self.get_dataset(dataset_id)

            # List all documents
            sdk_documents = dataset.list_documents()

            return sdk_documents

        except Exception as e:
            raise RuntimeError(f"Error getting all documents: {str(e)}") from e

    def update_document(self, dataset_id: str, document_id: str,
                        options: RagFlowUpdateDocumentOptions) -> Document:
        """Update a document (limited support in SDK)."""
        document = self.get_document(dataset_id, document_id)

        rag_doc = document.update({
            'display_name': options.display_name,
            'meta_fields': options.meta_fields
        })

        return rag_doc

    def delete_documents(self, dataset_id: str, document_ids: List[str]) -> None:
        """Delete documents using SDK."""
        try:
            # Get dataset object using our helper method
            dataset = self.get_dataset(dataset_id)

            # Delete documents
            dataset.delete_documents(ids=document_ids)

        except Exception as e:
            raise RuntimeError(f"Error deleting documents: {str(e)}") from e

    def delete_document(self, dataset_id: str, document_id: str) -> None:
        """Delete a single document using SDK."""
        self.delete_documents(dataset_id, [document_id])

    def get_document(self, dataset_id: str, document_id: str) -> Document:
        """Get a single document using SDK."""
        dataset = self.get_dataset(dataset_id)

        response = dataset.list_documents(id=document_id)

        if len(response) == 0:
            raise ValueError(f"Document with ID {document_id} not found")

        return response[0]

    def parse_documents(self, dataset_id: str, document_ids: List[str]) -> None:
        """Parse documents using SDK."""

        try:
            # Get dataset object using our helper method
            dataset = self.get_dataset(dataset_id)

            # Parse documents
            dataset.async_parse_documents(document_ids=document_ids)

        except Exception as e:
            raise RuntimeError(f"Error parsing documents: {str(e)}") from e

    def stop_parsing_documents(self, dataset_id: str, document_ids: List[str]) -> None:
        """Stop parsing documents (may not be supported in SDK)."""
        # SDK may not support stopping document parsing
        raise NotImplementedError("Stop parsing not supported in current SDK version")

    ################################# CHUNK MANAGEMENT #################################

    def retrieve_chunks(self, dataset_id: str, query: str, top_k: int = 5, similarity_threshold: float = 0.0,
                        vector_similarity_weight: float = 0.3) -> dict:
        """Retrieve chunks using SDK."""
        client = self._get_client()

        try:
            # Retrieve chunks using SDK
            retrieved_chunks = client.retrieve(
                question=query,
                dataset_ids=[dataset_id],
                similarity_threshold=similarity_threshold,
                vector_similarity_weight=vector_similarity_weight,
                top_k=top_k
            )

            return retrieved_chunks

        except Exception as e:
            raise RuntimeError(f"Error retrieving chunks: {str(e)}") from e

    def get_document_chunks(self, dataset_id: str, document_id: str,
                            keyword: Optional[str] = None,
                            page: int = 1,
                            limit: int = 20) -> List[Chunk]:
        """Get chunks for a specific document using SDK."""
        try:
            # Get document object
            document = self.get_document(dataset_id, document_id)

            # Retrieve chunks for the document
            retrieved_chunks = document.list_chunks(keywords=keyword, page=page, page_size=limit)

            return retrieved_chunks

        except Exception as e:
            raise RuntimeError(f"Error retrieving document chunks: {str(e)}") from e

    ################################# CHAT MANAGEMENT #################################

    def create_chat(self, chat: RagFlowCreateChatRequest) -> Chat:
        """Create chat assistant using SDK."""
        client = self._get_client()

        try:
            sdk_chat = client.create_chat(
                name=chat.name,
                dataset_ids=chat.knowledgebases,
                llm=chat.llm
            )

            return sdk_chat

        except Exception as e:
            raise RuntimeError(f"Error creating chat: {str(e)}") from e

    def list_chats(self, page: int = 1, page_size: int = 10) -> List[Chat]:
        """List chats using SDK."""
        client = self._get_client()

        try:
            sdk_chats = client.list_chats()

            # Apply pagination
            start_idx = (page - 1) * page_size
            end_idx = start_idx + page_size

            return sdk_chats[start_idx:end_idx]

        except Exception as e:
            raise RuntimeError(f"Error listing chats: {str(e)}") from e

    def update_chat(self, chat_id: str, updates: RagFlowUpdateChatRequest) -> Chat:
        """Update chat (limited support in SDK)."""
        raise NotImplementedError("Chat updates not supported in current SDK version")

    def delete_chats(self, chat_ids: List[str]) -> None:
        """Delete chats using SDK."""
        client = self._get_client()

        try:
            client.delete_chats(ids=chat_ids)
        except Exception as e:
            raise RuntimeError(f"Error deleting chats: {str(e)}") from e

    ################################# SESSION MANAGEMENT #################################

    def get_chat(self, chat_id: str) -> Chat:
        """Get chat using SDK."""
        client = self._get_client()

        try:
            # Get chat object
            chats = client.list_chats(id=chat_id)

            if len(chats) == 0:
                raise ValueError(f"Chat {chat_id} not found")

            return chats[0]

        except Exception as e:
            raise RuntimeError(f"Error getting chat: {str(e)}") from e

    def create_session(self, chat_id: str, session: RagFlowCreateSessionRequest) -> Session:
        """Create session using SDK."""

        try:
            # Get chat object
            chat = self.get_chat(chat_id=chat_id)

            # Create session
            sdk_session = chat.create_session(name=session.name)

            return sdk_session

        except Exception as e:
            raise RuntimeError(f"Error creating session: {str(e)}") from e

    def list_sessions(self, chat_id: str, page: int = 1, page_size: int = 10) -> List[Session]:
        """List sessions using SDK."""

        try:
            # Get chat object
            chat = self.get_chat(chat_id=chat_id)

            # List sessions
            sdk_sessions = chat.list_sessions()

            # Apply pagination
            start_idx = (page - 1) * page_size
            end_idx = start_idx + page_size

            return sdk_sessions[start_idx:end_idx]

        except Exception as e:
            raise RuntimeError(f"Error listing sessions: {str(e)}") from e

    def delete_sessions(self, chat_id: str, session_ids: List[str]) -> None:
        """Delete sessions using SDK."""

        try:
            # Get chat object
            chat = self.get_chat(chat_id=chat_id)

            # Delete sessions
            chat.delete_sessions(ids=session_ids)

        except Exception as e:
            raise RuntimeError(f"Error deleting sessions: {str(e)}") from e

    def get_session(self, chat_id: str, session_id: str) -> Session:
        """Get session using SDK."""

        try:
            # Get chat object
            chat = self.get_chat(chat_id=chat_id)

            sessions = chat.list_sessions(id=session_id)  # Ensure session exists

            if len(sessions) == 0:
                raise ValueError(f"Session {session_id} not found in chat {chat_id}")

            return sessions[0]

        except Exception as e:
            raise RuntimeError(f"Error getting session: {str(e)}") from e

    def ask_stream(self, chat_id: str, query: str, session_id: Optional[str] = None) -> Generator[Any, None, None]:
        """Ask question using SDK with streaming."""
        try:
            # Get chat object
            chat = self.get_chat(chat_id=chat_id)

            # Get or create session
            session: Session = None
            if session_id:
                sessions = chat.list_sessions(id=session_id)
                if len(sessions) > 0:
                    session = sessions[0]

            if not session:
                session = chat.create_session(name="default_session")

            # Ask question with streaming - return raw SDK responses
            for chunk in session.ask(question=query, stream=True):
                yield chunk

        except Exception as e:
            raise RuntimeError(f"Error asking question: {str(e)}") from e

    @staticmethod
    def from_credentials(credentials: CredentialsDataOther):
        """Create RagFlowService from credentials.

        Parameters
        ----------
        credentials : CredentialsDataOther
            Credentials containing base_url and api_key

        Returns
        -------
        RagFlowService
            Configured service instance

        Raises
        ------
        ValueError
            If required credentials are missing
        """
        if 'route' not in credentials.data:
            raise ValueError("The credentials must contain the field 'route'")
        if 'api_key' not in credentials.data:
            raise ValueError("The credentials must contain the field 'api_key'")
        return RagFlowService(credentials.data['route'], credentials.data['api_key'])
