
import streamlit as st
from gws_core import Credentials, CredentialsDataOther

from gws_ai_toolkit.rag.common.rag_datahub_service import DatahubRagService
from gws_ai_toolkit.rag.common.rag_enums import RagProvider
from gws_ai_toolkit.rag.common.rag_service_factory import RagServiceFactory


class DatahubRagAppState:
    """Class to manage the state of the app with support for both Dify and RagFlow.
    """

    CHAT_CREDENTIALS = "chat_credentials"
    KNOWLEDGE_BASE_CREDENTIALS = "knowledge_base_credentials"
    KNOWLEDGE_BASE_ID = "knowledge_base_id"
    RAG_PROVIDER = "rag_provider"
    FILTER_RAG_WITH_USER_FOLDERS = "filter_rag_with_user_folders"

    @classmethod
    def init(cls, chat_credentials_name: str, knowledge_base_credentials_name: str,
             knowledge_base_id: str, rag_provider: RagProvider,
             filter_rag_with_user_folders: bool):
        """Initialize the session state variables."""
        cls.set_chat_credentials_name(chat_credentials_name)
        cls.set_knowledge_base_credentials_name(knowledge_base_credentials_name)
        cls.set_knowledge_base_id(knowledge_base_id)
        cls.set_rag_provider(rag_provider)
        cls.set_filter_rag_with_user_folders(filter_rag_with_user_folders)

    @classmethod
    def set_chat_credentials_name(cls, chat_credentials_name: str):
        current_credentials: CredentialsDataOther = st.session_state.get(cls.CHAT_CREDENTIALS)
        if current_credentials and current_credentials.meta.name == chat_credentials_name:
            return

        credentials = Credentials.find_by_name_and_check(chat_credentials_name)
        st.session_state[cls.CHAT_CREDENTIALS] = credentials.get_data_object()

    @classmethod
    def get_chat_credentials(cls) -> CredentialsDataOther:
        """Get the chat credentials from the session state."""
        return st.session_state.get(cls.CHAT_CREDENTIALS)

    @classmethod
    def set_knowledge_base_credentials_name(cls, knowledge_base_credentials_name: str):
        current_credentials: CredentialsDataOther = st.session_state.get(cls.KNOWLEDGE_BASE_CREDENTIALS)
        if current_credentials and current_credentials.meta.name == knowledge_base_credentials_name:
            return

        credentials = Credentials.find_by_name_and_check(knowledge_base_credentials_name)
        st.session_state[cls.KNOWLEDGE_BASE_CREDENTIALS] = credentials.get_data_object()

    @classmethod
    def get_knowledge_base_credentials(cls) -> CredentialsDataOther:
        """Get the knowledge base credentials from the session state."""
        return st.session_state.get(cls.KNOWLEDGE_BASE_CREDENTIALS)

    @classmethod
    def set_knowledge_base_id(cls, knowledge_base_id: str):
        """Set the knowledge base id in the session state."""
        st.session_state[cls.KNOWLEDGE_BASE_ID] = knowledge_base_id

    @classmethod
    def get_knowledge_base_id(cls) -> str:
        """Get the knowledge base id from the session state."""
        return st.session_state.get(cls.KNOWLEDGE_BASE_ID)

    @classmethod
    def set_rag_provider(cls, rag_provider: RagProvider):
        """Set the RAG provider in the session state."""
        st.session_state[cls.RAG_PROVIDER] = rag_provider

    @classmethod
    def get_rag_provider(cls) -> RagProvider:
        """Get the RAG provider from the session state."""
        return st.session_state.get(cls.RAG_PROVIDER, "dify")

    @classmethod
    def get_datahub_knowledge_rag_service(cls) -> DatahubRagService:
        """Get the DataHub RAG service for knowledge base operations."""
        provider = cls.get_rag_provider()
        rag_service = RagServiceFactory.create_service(provider, cls.get_knowledge_base_credentials())
        return DatahubRagService(rag_service, cls.get_knowledge_base_id())

    @classmethod
    def get_datahub_chat_rag_service(cls) -> DatahubRagService:
        """Get the DataHub RAG service for chat operations."""
        provider = cls.get_rag_provider()
        rag_service = RagServiceFactory.create_service(provider, cls.get_chat_credentials())
        return DatahubRagService(rag_service, cls.get_knowledge_base_id())

    @classmethod
    def is_filter_rag_with_user_folders(cls) -> bool:
        """Check if RAG should be filtered with user folders."""
        return st.session_state.get(cls.FILTER_RAG_WITH_USER_FOLDERS)

    @classmethod
    def set_filter_rag_with_user_folders(cls, value: bool):
        """Set whether to filter RAG with user folders."""
        st.session_state[cls.FILTER_RAG_WITH_USER_FOLDERS] = value
