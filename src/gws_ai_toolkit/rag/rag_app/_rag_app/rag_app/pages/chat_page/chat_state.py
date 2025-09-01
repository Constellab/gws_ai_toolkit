import uuid
from typing import List

from gws_ai_toolkit.rag.common.rag_models import (RagChatEndStreamResponse,
                                                  RagChatStreamResponse,
                                                  RagChunk)
from gws_ai_toolkit.rag.rag_app._rag_app.rag_app.components.generic_chat.chat_config import \
    ChatStateBase
from gws_ai_toolkit.rag.rag_app._rag_app.rag_app.components.generic_chat.generic_chat_class import \
    ChatMessageText

from ...states.rag_main_state import RagAppState


class ChatState(RagAppState, ChatStateBase):
    """State management for the chat functionality."""

    async def call_ai_chat(self, user_message: str):
        """Get streaming response from the assistant."""

        datahub_rag_service = await self.get_chat_rag_app_service
        if not datahub_rag_service:
            return

        full_response = ""
        end_message_response = None
        current_assistant_message = None

        # # Get current user ID
        # current_user = self.get_current_user()
        # user_id = current_user.id if current_user else "anonymous"

        # Stream the response
        for chunk in datahub_rag_service.send_message_stream(
            query=user_message,
            conversation_id=self.conversation_id,
            user=None,  # TODO handle user
            chat_id=await self.get_chat_id,
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
