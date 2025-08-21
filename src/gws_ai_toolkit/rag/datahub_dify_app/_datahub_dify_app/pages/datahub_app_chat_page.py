import uuid
from typing import List, Literal, Optional

import streamlit as st
from gws_ai_toolkit.rag.common.rag_models import (RagChatEndStreamResponse,
                                                  RagChatStreamResponse,
                                                  RagChunk)
from gws_ai_toolkit.rag.datahub_dify_app._datahub_dify_app.datahub_app_state import \
    DatahubRagAppState
from gws_core.core.model.model_dto import BaseModelDTO
from gws_core.core.utils.logger import Logger
from gws_core.space.space_service import SpaceService
from gws_core.streamlit import StreamlitContainers, StreamlitState


class ChatMessage(BaseModelDTO):
    role: Literal['user', 'assistant']
    content: str
    id: str
    sources: Optional[List[RagChunk]] = []


class DataHubRagAppChatPageState:

    root_folder_limit: int = None
    # if true the RAG will be filtered with user folders
    filter_rag_with_user_folders: bool = None
    state_key: str = None
    root_folder_ids: List[str] = None
    chat_messages: List[ChatMessage] = None
    conversation_id: Optional[str] = None
    chat_id: Optional[str] = None  # define in ragflow

    def __init__(self, root_folder_limit: int, filter_rag_with_user_folders: bool,
                 chat_id: Optional[str],
                 key: str):
        """Initialize the state with default values"""
        self.root_folder_limit = root_folder_limit
        self.filter_rag_with_user_folders = filter_rag_with_user_folders
        self.chat_id = chat_id
        self.state_key = key
        self.root_folder_ids = []
        self.chat_messages = []
        self.conversation_id = None

    @classmethod
    def init(cls, root_folder_limit: int,
             filter_rag_with_user_folders: bool,
             chat_id: Optional[str] = None,
             key: str = 'datahub-dify-app-chat-page-state'):
        """
        Initialize the session state for the chat page.
        """
        if key in st.session_state:
            return st.session_state[key]

        state = cls(root_folder_limit, filter_rag_with_user_folders, chat_id, key)
        st.session_state[key] = state
        return state

    def get_root_folder_limit(self) -> int:
        """Get the root folder limit from the state."""
        return self.root_folder_limit

    def get_root_folder_ids(self) -> List[str]:
        """Get the root folders from the state."""
        if not self.filter_rag_with_user_folders:
            return []
        if not self.root_folder_ids:
            try:
                # Get all the user root folders from space
                folders = SpaceService.get_instance().get_all_current_user_root_folders()
                if not folders:
                    st.error("The user accessible folders could not be found.")

                # For dev purspose to have folder without the space running
                # folders: List[SpaceFolder] = list(SpaceFolder.get_roots())
                self.root_folder_ids = [folder.id for folder in folders]
            except Exception as e:
                Logger.error(f"Error while retrieving user accessible folders: {e}")
                Logger.log_exception_stack_trace(e)
                st.error("Could no retrieve the user accessible folders. Please retry later.")
                st.stop()

        return self.root_folder_ids

    def get_chat_messages(self) -> List[ChatMessage]:
        """Get the chat messages history from the state."""
        return self.chat_messages

    def add_chat_message(self, role: Literal['user', 'assistant'], content: str,
                         sources: Optional[List[RagChunk]] = None):
        """Add a new message to the chat history."""
        message = ChatMessage(
            role=role,
            content=content,
            id=str(uuid.uuid4()),
            sources=sources or []
        )
        self.chat_messages.append(message)

    def get_conversation_id(self) -> Optional[str]:
        """Get the current conversation ID."""
        return self.conversation_id

    def set_conversation_id(self, conversation_id: str):
        """Set the conversation ID."""
        self.conversation_id = conversation_id

    def get_chat_id(self) -> Optional[str]:
        """Get the current chat ID."""
        return self.chat_id

    def clear_chat(self):
        """Clear the chat history."""
        self.chat_messages = []
        self.conversation_id = None


def render_page(chat_state: DataHubRagAppChatPageState):

    with StreamlitContainers.container_centered('chat_page'):
        col1, col2 = StreamlitContainers.columns_with_fit_content(key='header-button', cols=[1, 'fit-content'],
                                                                  vertical_align_items='center')

        with col1:
            st.title("AI Chat")

        with col2:
            if st.button("Clear Chat History", icon=':material/replay:'):
                chat_state.clear_chat()
                st.rerun()

        # Display chat messages
        for message in chat_state.get_chat_messages():
            with st.chat_message(message.role):
                st.write(message.content)
                _render_sources(message)

        # Check if last message is from the user and needs a response
        messages = chat_state.get_chat_messages()
        last_message = messages[-1] if messages else None
        if last_message and last_message.role == "user":
            render_stream_response(last_message.content, chat_state)

        # Chat input
        if prompt := st.chat_input("Ask something..."):
            # Add user message to chat history
            chat_state.add_chat_message("user", prompt)
            st.rerun()


def _render_sources(message: ChatMessage):
    # Display sources if available
    if message.sources:
        with st.expander("Sources"):
            # Type source to RagChunk
            for source in message.sources:

                col1, col2, col3 = StreamlitContainers.columns_with_fit_content(
                    key=f'source_{message.id}_{source.document_name}_header',
                    cols=[1, 'fit-content', 'fit-content'],
                    vertical_align_items='center')
                with col1:
                    st.markdown(f"📄 **{source.document_name}** (Score: {source.score:.2f})")


def render_stream_response(user_prompt: str, chat_state: DataHubRagAppChatPageState):
    if st.session_state.get("chat_is_streaming", False):
        return
    st.session_state["chat_is_streaming"] = True

    datahub_rag_service = DatahubRagAppState.get_datahub_chat_rag_service()
    user_folders_ids = chat_state.get_root_folder_ids()

    if len(user_folders_ids) > chat_state.get_root_folder_limit():
        st.warning(
            f"You have access to too many root folders ({len(user_folders_ids)}). Only the first {chat_state.get_root_folder_limit()} folders will be used.")

    user_folders_ids = user_folders_ids[:chat_state.get_root_folder_limit()]
    # Display assistant response with streaming
    with st.chat_message("assistant"):
        response_placeholder = st.empty()
        full_response = ""

        try:
            # Stream the response using the RagService
            end_message_response = None

            # Process the streaming response
            for chunk in datahub_rag_service.send_message_stream(
                user_root_folder_ids=user_folders_ids,
                query=user_prompt,
                conversation_id=chat_state.get_conversation_id(),
                user=StreamlitState.get_current_user().id,
                chat_id=chat_state.get_chat_id(),
                inputs={},
            ):
                # Handle both abstracted RAG responses and responses
                if isinstance(chunk, (RagChatStreamResponse)):
                    if chunk.is_from_beginning:
                        # If it's the beginning of the response, reset the full response
                        full_response = chunk.answer
                    else:
                        full_response += chunk.answer
                    response_placeholder.markdown(full_response + "▌")
                elif isinstance(chunk, (RagChatEndStreamResponse)):
                    # It's the end message response
                    end_message_response = chunk

            # Final response without cursor
            response_placeholder.markdown(full_response)

            # Update conversation ID if returned (handle both response types)
            session_id = None
            sources: List[RagChunk] = []

            if end_message_response:
                # Handle response
                if isinstance(end_message_response, RagChatStreamResponse):
                    session_id = end_message_response.session_id

                # Handle abstracted RAG response
                elif isinstance(end_message_response, RagChatEndStreamResponse):
                    session_id = end_message_response.session_id
                    if end_message_response.sources:
                        for source in end_message_response.sources:
                            if source.document_id not in [s.document_id for s in sources]:
                                sources.append(source)

                if session_id:
                    chat_state.set_conversation_id(session_id)

            # Add assistant response to chat history
            chat_state.add_chat_message("assistant", full_response, sources)

            st.rerun()

        except Exception as e:
            st.error(f"Error: {str(e)}")
            return
        finally:
            st.session_state["chat_is_streaming"] = False
