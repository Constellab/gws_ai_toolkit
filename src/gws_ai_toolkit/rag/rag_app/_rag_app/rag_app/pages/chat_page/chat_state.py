import uuid
from typing import List

import reflex as rx
from gws_core import Logger, SpaceService

from gws_ai_toolkit.rag.common.rag_models import (RagChatEndStreamResponse,
                                                  RagChatStreamResponse,
                                                  RagChunk)
from gws_ai_toolkit.rag.rag_app._rag_app.rag_app.components.generic_chat.chat_config import \
    ChatStateBase
from gws_ai_toolkit.rag.rag_app._rag_app.rag_app.components.generic_chat.generic_chat_class import \
    ChatMessage

from ...states.main_state import RagAppState


class ChatState(RagAppState, ChatStateBase):
    """State management for the chat functionality."""

    root_folder_ids: List[str] = []

    def _get_root_folder_ids(self) -> List[str]:
        """Get the root folders from user access."""
        # if not self.check_authentication():
        #     return []

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

    async def call_ai_chat(self, user_message: str):
        """Get streaming response from the assistant."""

        datahub_rag_service = self.get_datahub_chat_rag_service
        if not datahub_rag_service:
            return

        user_folders_ids = self._get_root_folder_ids()

        # Limit folders if needed
        if len(user_folders_ids) > self.get_root_folder_limit:
            user_folders_ids = user_folders_ids[:self.get_root_folder_limit]

        full_response = ""
        end_message_response = None
        current_assistant_message = None

        # # Get current user ID
        # current_user = self.get_current_user()
        # user_id = current_user.id if current_user else "anonymous"

        # Stream the response
        for chunk in datahub_rag_service.send_message_stream(
            user_root_folder_ids=user_folders_ids,
            query=user_message,
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
                    self.set_conversation_id(session_id)

        # Update final message with sources if we have them
        await self.update_current_message_sources(sources)
