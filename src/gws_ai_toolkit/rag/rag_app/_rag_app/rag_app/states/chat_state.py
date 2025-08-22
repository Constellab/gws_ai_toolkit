import uuid
from typing import List, Literal, Optional

import reflex as rx
from gws_ai_toolkit.rag.common.rag_models import (RagChatEndStreamResponse,
                                                  RagChatStreamResponse,
                                                  RagChunk)
from gws_core.core.model.model_dto import BaseModelDTO
from gws_core.core.utils.logger import Logger
from gws_core.space.space_service import SpaceService

from .main_state import RagAppState


class ChatMessage(BaseModelDTO):
    role: Literal['user', 'assistant']
    content: str
    id: str
    sources: Optional[List[RagChunk]] = []


class ChatState(RagAppState):
    """State management for the chat functionality."""

    # Chat state
    chat_messages: List[ChatMessage] = []
    current_message: str = ""
    is_streaming: bool = False
    conversation_id: Optional[str] = None
    root_folder_ids: List[str] = []

    # Current response message being streamed
    current_response_message: Optional[ChatMessage] = None

    @rx.var
    def display_messages(self) -> List[ChatMessage]:
        """Get messages for UI display excluding current streaming message"""

        return self.chat_messages

    @rx.var
    def current_response_display(self) -> Optional[ChatMessage]:
        """Get the current response message for separate display"""
        return self.current_response_message

    @rx.var
    def get_conversation_id(self) -> Optional[str]:
        """Get the current conversation ID."""
        return self.conversation_id

    def _get_root_folder_ids(self) -> List[str]:
        """Get the root folders from user access."""
        if not self.check_authentication():
            return []

        if not self.is_filter_rag_with_user_folders:
            return []

        if not self.root_folder_ids:
            try:
                folders = SpaceService.get_instance().get_all_current_user_root_folders()
                if folders:
                    self.root_folder_ids = [folder.id for folder in folders]
            except Exception as e:
                Logger.error(f"Error while retrieving user accessible folders: {e}")

        return self.root_folder_ids

    async def update_current_response_message(self, message: ChatMessage) -> None:
        """Set the current streaming response message"""
        async with self:
            self.current_response_message = message

    async def close_current_message(self):
        """Close the current streaming message and add it to the chat history"""
        async with self:
            if self.current_response_message:
                self.chat_messages.append(self.current_response_message)
                self.current_response_message = None

    @rx.event(background=True)
    async def add_user_message(self, form_data: dict):
        """Add a user message to the chat history."""
        if not self.check_authentication():
            return

        content = form_data.get("message", "").strip()
        if not content:
            return

        message = ChatMessage(
            role="user",
            content=content,
            id=str(uuid.uuid4()),
            sources=[]
        )

        async with self:
            self.chat_messages.append(message)
            self.current_message = content

        # Trigger assistant response
        await self.get_assistant_response()

    async def get_assistant_response(self):
        """Get streaming response from the assistant."""

        async with self:
            if not self.check_authentication():
                return

            datahub_rag_service = self.get_datahub_chat_rag_service
            if not datahub_rag_service:
                return

            user_folders_ids = self._get_root_folder_ids()

            # Limit folders if needed
            if len(user_folders_ids) > self.get_root_folder_limit:
                user_folders_ids = user_folders_ids[:self.get_root_folder_limit]

            self.is_streaming = True
            message_to_process = self.current_message

        try:
            full_response = ""
            end_message_response = None
            current_assistant_message = None

            # # Get current user ID
            # current_user = self.get_current_user()
            # user_id = current_user.id if current_user else "anonymous"

            # Stream the response
            for chunk in datahub_rag_service.send_message_stream(
                user_root_folder_ids=user_folders_ids,
                query=message_to_process,
                conversation_id=self.conversation_id,
                user=None,  # TODO handle user
                chat_id=self.get_chat_id,
                inputs={},
            ):
                if isinstance(chunk, RagChatStreamResponse):
                    if chunk.is_from_beginning:
                        full_response = chunk.answer
                        # Create new message for streaming
                        current_assistant_message = ChatMessage(
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
            sources: List[RagChunk] = []

            if end_message_response:
                if isinstance(end_message_response, RagChatStreamResponse):
                    session_id = end_message_response.session_id
                elif isinstance(end_message_response, RagChatEndStreamResponse):
                    session_id = end_message_response.session_id
                    if end_message_response.sources:
                        for source in end_message_response.sources:
                            if source.document_id not in [s.document_id for s in sources]:
                                sources.append(source)

                async with self:
                    if session_id:
                        self.conversation_id = session_id

            # Update final message with sources if we have them
            if current_assistant_message and sources:
                async with self:
                    current_assistant_message.sources = sources

            # Close the streaming message (adds it to chat history)
            await self.close_current_message()

        except Exception as e:
            Logger.error(f"Error in assistant response: {str(e)}")
            Logger.log_exception_stack_trace(e)
            error_message = ChatMessage(
                role="assistant",
                content=f"Error: {str(e)}",
                id=str(uuid.uuid4()),
                sources=[]
            )
            await self.update_current_response_message(error_message)
            await self.close_current_message()
        finally:
            async with self:
                self.is_streaming = False
                self.current_message = ""

    @rx.event
    def clear_chat(self):
        """Clear the chat history."""
        if not self.check_authentication():
            return

        self.chat_messages = []
        self.conversation_id = None
        self.current_response_message = None
        self.current_message = ""
