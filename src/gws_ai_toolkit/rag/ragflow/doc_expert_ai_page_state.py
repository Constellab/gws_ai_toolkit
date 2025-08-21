from typing import Literal, Optional

import streamlit as st
from gws_ai_toolkit.rag.ragflow.ragflow_class import RagFlowRetrieveResponse
from gws_ai_toolkit.rag.ragflow.ragflow_service import RagFlowService
from gws_core import BaseModelDTO
from gws_core.streamlit import StreamlitOpenAiChat, StreamlitRouter


class DocExpertAIPageConfig(BaseModelDTO):
    page_name: str
    page_emoji: str
    page_url: str
    system_prompt: str
    summary_prompt: Optional[str] = None
    default_dataset_id: str

    @classmethod
    def get_default_config(cls, default_dataset_id: str) -> 'DocExpertAIPageConfig':
        return DocExpertAIPageConfig(
            page_name='Doc AI Expert', page_emoji='🤖', page_url='doc-ai-expert',
            system_prompt="You are a document expert. You have access to the text of 1 document and you must answer question about the document: <doc>[DOC_CONTENT]</doc>.",
            # TODO add summary prompt
            summary_prompt=None,
            # summary_prompt="You are a document expert. You have access to the text of 1 document. You must summarize the document. You must not use any other information. Here is the text of the document: <doc>[DOC_CONTENT]</article>",
            default_dataset_id=default_dataset_id)


class DocAiExpertRagFlowDocument(BaseModelDTO):
    id: str
    name: str
    dataset_id: str


class DocExpertSelectedDocument(BaseModelDTO):
    chunks: list
    content: str
    summary: Optional[str] = None


class DocAiExpertPageState():

    state_key: str = None
    config: DocExpertAIPageConfig = None
    ragflow_service: RagFlowService = None
    default_dataset_id: str = None
    query: str = None
    documents_result: RagFlowRetrieveResponse = None
    selected_document: DocAiExpertRagFlowDocument = None
    selected_document_chunks: DocExpertSelectedDocument = None
    chat: StreamlitOpenAiChat = None
    similarity_threshold: float = None
    vector_similarity_weight: float = None
    top_k: int = None

    _chat_key: str = None

    def __init__(self, key: str, config: DocExpertAIPageConfig,
                 ragflow_service: RagFlowService):
        """Initialize the state with default values"""
        self.state_key = key
        self.config = config
        self.ragflow_service = ragflow_service
        self.default_dataset_id = None
        self.query = None
        self.documents_result = None
        self.selected_document = None
        self.selected_document_chunks = None
        self.chat = None
        self.similarity_threshold = 0.0
        self.vector_similarity_weight = 0.3
        self.top_k = 5
        self._chat_key = key + '-chat'

    @classmethod
    def init(cls, config: DocExpertAIPageConfig,
             ragflow_service: RagFlowService,
             key: str = 'doc-ai-expert-page-state'):
        """
        Initialize the session state for the article AI page.
        """
        if key in st.session_state:
            return st.session_state[key]

        state = cls(key, config, ragflow_service)
        st.session_state[key] = state
        return state

    @classmethod
    def get_instance(cls, key: str = 'doc-ai-expert-page-state') -> Optional['DocAiExpertPageState']:
        """
        Get the instance of the article AI page state.
        """
        if key not in st.session_state:
            return None
        return st.session_state[key]

    def reset(self):
        """
        Reset the state attributes to their default values.
        """
        self.query = None
        self.documents_result = None
        self.selected_document = None
        self.selected_document_chunks = None
        self.chat = None

    def select_document_and_navigate(self, document: DocAiExpertRagFlowDocument):
        """
        Select a document and reset other related attributes.
        It can be call from outside the expert page to set the document and then
        redirect to the expert page.
        """
        self.reset()
        self.selected_document = document
        StreamlitRouter.load_from_session().navigate(self.config.page_url)

    def get_status(self) -> Literal['SEARCH', 'SEARCH_RESULTS', 'DOCUMENT_CHAT', 'DOCUMENT_SELECTED_NOT_LOADED']:
        """
        Check the current state status based on attribute values.
        """
        # special case where a doc id is selected but the document chunks are not loaded
        if self.selected_document_chunks is not None:
            return 'DOCUMENT_CHAT'
        if self.selected_document is not None:
            return 'DOCUMENT_SELECTED_NOT_LOADED'
        if self.documents_result is not None:
            return 'SEARCH_RESULTS'
        return 'SEARCH'

    def get_documents_result(self) -> RagFlowRetrieveResponse:
        """
        Get the documents result.
        """
        return self.documents_result

    def set_documents_result(self, result: RagFlowRetrieveResponse):
        """
        Set the documents result.
        """
        self.documents_result = result

    def get_query(self) -> str:
        """
        Get the query.
        """
        return self.query

    def set_query(self, query: str):
        """
        Set the query.
        """
        self.query = query

    def get_selected_document(self) -> DocAiExpertRagFlowDocument:
        """
        Get the selected document.
        """
        return self.selected_document

    def set_selected_document(self, document: DocAiExpertRagFlowDocument):
        """
        Set the selected document.
        """
        self.selected_document = document

    def get_default_dataset_id(self) -> str:
        """
        Get the dataset ID.
        """
        return self.default_dataset_id

    def set_default_dataset_id(self, dataset_id: str):
        """
        Set the dataset ID.
        """
        self.default_dataset_id = dataset_id

    def get_selected_document_chunks(self) -> DocExpertSelectedDocument:
        """
        Get the selected document chunks.
        """
        return self.selected_document_chunks

    def set_selected_document_chunks(self, chunks: DocExpertSelectedDocument):
        """
        Set the selected document chunks.
        """
        self.selected_document_chunks = chunks

    def load_chat(self, system_prompt: str) -> StreamlitOpenAiChat:
        """
        Load or initialize the chat with the given system prompt.
        """
        if self.chat is None:
            self.chat = StreamlitOpenAiChat.load_from_session(key=self._chat_key, system_prompt=system_prompt)
        return self.chat

    def get_similarity_threshold(self) -> float:
        """
        Get the similarity threshold.
        """
        return self.similarity_threshold

    def set_similarity_threshold(self, threshold: float):
        """
        Set the similarity threshold.
        """
        self.similarity_threshold = threshold

    def get_vector_similarity_weight(self) -> float:
        """
        Get the vector similarity weight.
        """
        return self.vector_similarity_weight

    def set_vector_similarity_weight(self, weight: float):
        """
        Set the vector similarity weight.
        """
        self.vector_similarity_weight = weight

    def get_top_k(self) -> int:
        """
        Get the top_k value.
        """
        return self.top_k

    def set_top_k(self, top_k: int):
        """
        Set the top_k value.
        """
        self.top_k = top_k

    def get_document_url(self, document_id: str) -> str | None:
        """
        Override this method to return the document URL.
        """
        return None