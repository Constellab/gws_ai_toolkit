import uuid
from typing import Awaitable, Callable, List

import reflex as rx
from gws_core import BaseModelDTO

from gws_ai_toolkit.rag.common.rag_enums import RagProvider
from gws_ai_toolkit.rag.common.rag_models import (RagChatEndStreamResponse,
                                                  RagChatSource,
                                                  RagChatStreamResponse)

from ..chat_base.chat_message_class import ChatMessageText
from ..chat_base.chat_state_base import ChatStateBase
from ..rag_chat.config.rag_config_state import RagConfigState


class RagChatStateConfig(BaseModelDTO):
    rag_provider: RagProvider
    chat_id: str
    credentials_name: str


class RagChatState(ChatStateBase, rx.State):
    """State management for RAG (Retrieval Augmented Generation) chat functionality.
    
    This state class implements the main RAG chat system, providing intelligent
    conversations enhanced with document knowledge from indexed sources. It integrates
    with various RAG providers (Dify, RagFlow) and handles streaming responses with
    source citations.
    
    Key Features:
        - RAG-enhanced conversation with document knowledge
        - Streaming AI responses with real-time updates
        - Source citation and document references
        - Integration with multiple RAG providers
        - Conversation history and persistence
        - Error handling and fallback mechanisms
        
    The state connects to configured RAG services and processes user queries
    by retrieving relevant document chunks and generating contextual responses
    with proper source attribution.
    """

    _loader: Callable[[rx.State], Awaitable[RagChatStateConfig]] | None = None

    @classmethod
    def set_loader(cls, loader: Callable[[rx.State], Awaitable[RagChatStateConfig]]) -> None:
        """Set the loader function to get the path of the config file."""
        cls._loader = loader

    async def call_ai_chat(self, user_message: str):
        """Get streaming response from the assistant."""

        rag_app_state: RagConfigState
        async with self:
            rag_app_state = await self.get_state(RagConfigState)

        datahub_rag_service = await rag_app_state.get_chat_rag_app_service()
        if not datahub_rag_service:
            raise ValueError("RAG chat service not available")

        full_response = ""
        end_message_response = None
        current_assistant_message = None

        # # Get current user ID
        # current_user = self.get_current_user()
        # user_id = current_user.id if current_user else "anonymous"

        # Stream the response
        chat_id = await rag_app_state.get_chat_id()
        if not chat_id:
            raise ValueError("Chat ID is not configured")
        for chunk in datahub_rag_service.send_message_stream(
            query=user_message,
            conversation_id=self.conversation_id,
            user=None,  # TODO handle user
            chat_id=chat_id,
        ):
            if isinstance(chunk, RagChatStreamResponse):
                if chunk.is_from_beginning:
                    full_response = chunk.answer
                    # Create new message for streaming
                    current_assistant_message = ChatMessageText(
                        role="assistant",
                        content=full_response,
                        id=str(uuid.uuid4()),
                        sources=[]
                    )
                    await self.update_current_response_message(current_assistant_message)
                else:
                    full_response += chunk.answer
                    # Update the current streaming message
                    if current_assistant_message:
                        async with self:
                            current_assistant_message.content = full_response
            elif isinstance(chunk, RagChatEndStreamResponse):
                end_message_response = chunk

        # Process the final response
        session_id = None
        sources: List[RagChatSource] = []

        if end_message_response:
            if isinstance(end_message_response, RagChatStreamResponse):
                session_id = end_message_response.session_id
            elif isinstance(end_message_response, RagChatEndStreamResponse):
                session_id = end_message_response.session_id
                if end_message_response.sources:
                    sources = end_message_response.sources

            async with self:
                if session_id:
                    self.set_conversation_id(session_id)

        # Update final message with sources if we have them
        await self.update_current_message_sources(sources)

    async def close_current_message(self):
        """Close the current streaming message and add it to the chat history, then save to conversation history."""
        await super().close_current_message()
        # Save conversation after message is added to history
        await self._save_conversation_to_history()

    async def _save_conversation_to_history(self):
        """Save current conversation to history with configuration."""

        await self.save_conversation_to_history("RAG", {})
