from typing import Generator, List, Literal, Union

from gws_ai_toolkit.rag.ragflow.ragflow_class import (
    RagFlowAskRequest, RagFlowChat, RagFlowChatEndStreamResponse,
    RagFlowChatStreamResponse, RagFlowChunk, RagFlowCreateChatRequest,
    RagFlowCreateDatasetRequest, RagFlowCreateSessionRequest, RagFlowDataset,
    RagFlowDocument, RagFlowListChatsResponse, RagFlowListDatasetsResponse,
    RagFlowListDocumentsResponse, RagFlowListSessionsResponse,
    RagFlowRetrieveResponse, RagFlowSendDocumentResponse, RagFlowSession,
    RagFlowUpdateChatRequest, RagFlowUpdateDatasetRequest)
from gws_core import CredentialsDataOther
from ragflow_sdk import DataSet, Document, RAGFlow, Session


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

    def create_dataset(self, dataset: RagFlowCreateDatasetRequest) -> RagFlowDataset:
        """Create a new dataset/knowledgebase using SDK.

        Parameters
        ----------
        dataset : RagFlowCreateDatasetRequest
            Dataset configuration

        Returns
        -------
        RagFlowDataset
            Created dataset information
        """
        client = self._get_client()

        try:
            sdk_dataset = client.create_dataset(
                name=dataset.name,
                chunk_method=dataset.parse_method if hasattr(dataset, 'parse_method') else 'naive',
                permission=dataset.permission if hasattr(dataset, 'permission') else 'me'
            )

            # Convert SDK dataset to our format
            return RagFlowDataset(
                id=sdk_dataset.id,
                name=sdk_dataset.name,
                avatar=dataset.avatar if hasattr(dataset, 'avatar') else None,
                description=dataset.description if hasattr(dataset, 'description') else None,
                language=dataset.language if hasattr(dataset, 'language') else 'English',
                embedding_model=dataset.embedding_model if hasattr(dataset, 'embedding_model') else 'default',
                permission=dataset.permission if hasattr(dataset, 'permission') else 'me',
                parse_method=dataset.parse_method if hasattr(dataset, 'parse_method') else 'naive',
                chunk_count=0,
                document_count=0,
                created_by='user',
                tenant_id='default',
                created_at='',
                updated_at=''
            )
        except Exception as e:
            raise RuntimeError(f"Error creating dataset: {str(e)}") from e

    def get_dataset(self, dataset_id: str) -> DataSet:
        """Get a single dataset by ID using list_datasets."""
        client = self._get_client()
        dk_datasets = client.list_datasets(id=dataset_id)

        if len(dk_datasets) == 0:
            raise ValueError(f"Dataset {dataset_id} not found")

        return dk_datasets[0]

    def list_datasets(self, page: int = 1, page_size: int = 10) -> RagFlowListDatasetsResponse:
        """List all datasets/knowledgebases using SDK."""
        client = self._get_client()

        try:
            sdk_datasets = client.list_datasets()

            # Convert SDK datasets to our format
            datasets = []
            start_idx = (page - 1) * page_size
            end_idx = start_idx + page_size

            for sdk_dataset in sdk_datasets[start_idx:end_idx]:
                dataset = RagFlowDataset(
                    id=sdk_dataset.id,
                    name=sdk_dataset.name,
                    avatar=None,
                    description=None,
                    language='English',
                    embedding_model='default',
                    permission='me',
                    parse_method='naive',
                    chunk_count=getattr(sdk_dataset, 'chunk_count', 0),
                    document_count=getattr(sdk_dataset, 'document_count', 0),
                    created_by='user',
                    tenant_id='default',
                    created_at='',
                    updated_at=''
                )
                datasets.append(dataset)

            return RagFlowListDatasetsResponse(
                code=0,
                message='success',
                data=datasets
            )
        except Exception as e:
            raise RuntimeError(f"Error listing datasets: {str(e)}") from e

    def update_dataset(self, dataset_id: str, updates: RagFlowUpdateDatasetRequest) -> RagFlowDataset:
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
                         filenames: List[str] = None) -> RagFlowSendDocumentResponse:
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
            doc_response: List[RagFlowDocument] = []

            for ragflow_doc in ragflow_response:
                doc = self._document_to_ragflow_document(ragflow_doc)
                doc_response.append(doc)

            return RagFlowSendDocumentResponse(
                code=0,
                message='success',
                data=doc_response
            )

        except Exception as e:
            raise RuntimeError(f"Error uploading documents: {str(e)}") from e

    def upload_document(self, doc_paths: str, dataset_id: str,
                        filename: str = None) -> RagFlowDocument:
        """Upload multiple documents using SDK."""
        response = self.upload_documents([doc_paths], dataset_id, [filename] if filename else None)
        return response.data[0]

    def _document_to_ragflow_document(self, document: Document) -> RagFlowDocument:
        """Convert SDK Document to RagFlowDocument."""
        parsed: Literal['DONE', 'PENDING', 'RUNNING', 'ERROR'] = None
        if document.run == 'UNSTART':
            parsed = 'PENDING'
        elif document.run == 'DONE':
            parsed = 'DONE'
        elif document.run == 'RUNNING':
            parsed = 'RUNNING'
        else:  # FAIL
            parsed = 'ERROR'
        return RagFlowDocument(
            id=document.id,
            name=document.name,
            size=document.size,
            knowledgebase_id=document.dataset_id,
            type=document.type,
            parsed=parsed
        )

    def list_documents(self, dataset_id: str, page: int = 1, page_size: int = 10) -> RagFlowListDocumentsResponse:
        """List documents using SDK."""
        try:
            # Get dataset object using our helper method
            dataset = self.get_dataset(dataset_id)

            # List documents
            sdk_documents = dataset.list_documents()

            # Convert to our format with pagination
            start_idx = (page - 1) * page_size
            end_idx = start_idx + page_size

            documents = []
            for sdk_doc in sdk_documents[start_idx:end_idx]:
                doc = self._document_to_ragflow_document(sdk_doc)
                documents.append(doc)

            return RagFlowListDocumentsResponse(
                code=0,
                message='success',
                data=documents
            )

        except Exception as e:
            raise RuntimeError(f"Error listing documents: {str(e)}") from e

    def get_all_documents(self, dataset_id: str) -> List[RagFlowDocument]:
        """Get all documents using SDK."""

        try:
            # Get dataset object using our helper method
            dataset = self.get_dataset(dataset_id)

            # List all documents
            sdk_documents = dataset.list_documents()

            documents = []
            for sdk_doc in sdk_documents:
                doc = self._document_to_ragflow_document(sdk_doc)
                documents.append(doc)

            return documents

        except Exception as e:
            raise RuntimeError(f"Error getting all documents: {str(e)}") from e

    def update_document(self, doc_path: str, dataset_id: str, document_id: str,
                        filename: str = None) -> RagFlowDocument:
        """Update a document (limited support in SDK)."""
        self.delete_document(dataset_id, document_id)
        return self.upload_document(doc_path, dataset_id, filename)

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
                        vector_similarity_weight: float = 0.3) -> RagFlowRetrieveResponse:
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

            # Convert to our format


            chunks = []
            for chunk in retrieved_chunks.get('chunks', []):
                ragflow_chunk = RagFlowChunk(
                    id=chunk.get('id', ''),
                    content=chunk.get('content', ''),
                    document_id=chunk.get('document_id', ''),
                    document_name=chunk.get('document_name', ''),
                    dataset_id=dataset_id,
                )
                chunks.append(ragflow_chunk)

            return RagFlowRetrieveResponse(
                code=0,
                message='success',
                data={'chunks': chunks},
                chunks=chunks
            )

        except Exception as e:
            raise RuntimeError(f"Error retrieving chunks: {str(e)}") from e

    ################################# CHAT MANAGEMENT #################################

    def create_chat(self, chat: RagFlowCreateChatRequest) -> RagFlowChat:
        """Create chat assistant using SDK."""
        client = self._get_client()

        try:
            sdk_chat = client.create_chat(
                name=chat.name,
                dataset_ids=chat.knowledgebases,
                llm=chat.llm
            )

            return RagFlowChat(
                id=sdk_chat.id,
                name=sdk_chat.name,
                avatar=chat.avatar,
                knowledgebases=chat.knowledgebases,
                llm=chat.llm,
                prompt=chat.prompt,
                created_by='user',
                created_at='',
                updated_at=''
            )

        except Exception as e:
            raise RuntimeError(f"Error creating chat: {str(e)}") from e

    def list_chats(self, page: int = 1, page_size: int = 10) -> RagFlowListChatsResponse:
        """List chats using SDK."""
        client = self._get_client()

        try:
            sdk_chats = client.list_chats()

            # Apply pagination
            start_idx = (page - 1) * page_size
            end_idx = start_idx + page_size

            chats = []
            for sdk_chat in sdk_chats[start_idx:end_idx]:
                chat = RagFlowChat(
                    id=sdk_chat.id,
                    name=sdk_chat.name,
                    avatar=None,
                    knowledgebases=[],
                    llm={},
                    prompt='',
                    created_by='user',
                    created_at='',
                    updated_at=''
                )
                chats.append(chat)

            return RagFlowListChatsResponse(
                code=0,
                message='success',
                data=chats
            )

        except Exception as e:
            raise RuntimeError(f"Error listing chats: {str(e)}") from e

    def update_chat(self, chat_id: str, updates: RagFlowUpdateChatRequest) -> RagFlowChat:
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

    def create_session(self, chat_id: str, session: RagFlowCreateSessionRequest) -> RagFlowSession:
        """Create session using SDK."""
        client = self._get_client()

        try:
            # Get chat object
            chats = client.list_chats()
            chat = next((c for c in chats if c.id == chat_id), None)
            if not chat:
                raise ValueError(f"Chat {chat_id} not found")

            # Create session
            sdk_session = chat.create_session(name=session.name)

            return RagFlowSession(
                id=sdk_session.id,
                name=sdk_session.name,
                messages=[],
                chat_id=chat_id,
                created_at='',
                updated_at=''
            )

        except Exception as e:
            raise RuntimeError(f"Error creating session: {str(e)}") from e

    def list_sessions(self, chat_id: str, page: int = 1, page_size: int = 10) -> RagFlowListSessionsResponse:
        """List sessions using SDK."""
        client = self._get_client()

        try:
            # Get chat object
            chats = client.list_chats()
            chat = next((c for c in chats if c.id == chat_id), None)
            if not chat:
                raise ValueError(f"Chat {chat_id} not found")

            # List sessions
            sdk_sessions = chat.list_sessions()

            # Apply pagination
            start_idx = (page - 1) * page_size
            end_idx = start_idx + page_size

            sessions = []
            for sdk_session in sdk_sessions[start_idx:end_idx]:
                session = RagFlowSession(
                    id=sdk_session.id,
                    name=sdk_session.name,
                    messages=[],
                    chat_id=chat_id,
                    created_at='',
                    updated_at=''
                )
                sessions.append(session)

            return RagFlowListSessionsResponse(
                code=0,
                message='success',
                data=sessions
            )

        except Exception as e:
            raise RuntimeError(f"Error listing sessions: {str(e)}") from e

    def delete_sessions(self, chat_id: str, session_ids: List[str]) -> None:
        """Delete sessions using SDK."""
        client = self._get_client()

        try:
            # Get chat object
            chats = client.list_chats()
            chat = next((c for c in chats if c.id == chat_id), None)
            if not chat:
                raise ValueError(f"Chat {chat_id} not found")

            # Delete sessions
            chat.delete_sessions(ids=session_ids)

        except Exception as e:
            raise RuntimeError(f"Error deleting sessions: {str(e)}") from e

    def ask(self, chat_id: str, ask_request: RagFlowAskRequest) -> Generator[Union[RagFlowChatStreamResponse, RagFlowChatEndStreamResponse], None, None]:
        """Ask question using SDK with streaming."""
        client = self._get_client()

        try:
            # Get chat object
            chats = client.list_chats()
            chat = next((c for c in chats if c.id == chat_id), None)
            if not chat:
                raise ValueError(f"Chat {chat_id} not found")

            # Get or create session
            session: Session = None
            if ask_request.session_id:
                sessions = chat.list_sessions(id=ask_request.session_id)
                if len(sessions) > 0:
                    session = sessions[0]

            if not session:
                session = chat.create_session(name="default_session")

            # Ask question with streaming
            if ask_request.stream:
                for chunk in session.ask(question=ask_request.question, stream=True):
                    if chunk.reference:
                        print('kk')
                    if chunk.role == 'assistant':

                        if chunk.reference:
                            references: List[RagFlowChunk] = []
                            for ref in chunk.reference:
                                references.append(RagFlowChunk(
                                    id=ref['id'],
                                    content=ref['content'],
                                    document_id=ref['document_id'],
                                    document_name=ref['document_name'],
                                    dataset_id=ref['dataset_id']
                                ))
                            # Final response
                            yield RagFlowChatEndStreamResponse(
                                session_id=session.id,
                                message_id='',
                                reference=references
                            )
                        else:
                            yield RagFlowChatStreamResponse(
                                answer=chunk.content,
                                reference=[]
                            )

            else:
                # TODO TO FIX
                # Non-streaming response
                response = session.ask(question=ask_request.question, stream=False)
                yield RagFlowChatStreamResponse(
                    answer=response.get('answer', ''),
                    reference=response.get('reference', [])
                )
                yield RagFlowChatEndStreamResponse(
                    session_id=session.id,
                    message_id=response.get('message_id', ''),
                    reference=response.get('reference', [])
                )

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
