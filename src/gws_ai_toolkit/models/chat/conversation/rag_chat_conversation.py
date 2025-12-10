from collections.abc import Generator

from gws_ai_toolkit.models.chat.message.chat_message_types import ChatMessage
from gws_ai_toolkit.models.chat.message.chat_user_message import ChatUserMessageText
from gws_ai_toolkit.rag.common.base_rag_service import BaseRagService
from gws_ai_toolkit.rag.common.rag_models import (
    RagChatEndStreamResponse,
    RagChatSource,
    RagChatStreamResponse,
)

from .base_chat_conversation import BaseChatConversation, BaseChatConversationConfig


class RagChatConversation(BaseChatConversation[ChatUserMessageText]):
    """Chat conversation implementation for RAG (Retrieval Augmented Generation).

    This class handles RAG-based chat conversations with streaming support,
    storing messages during streaming and persisting them once the stream completes.
    """

    rag_service: BaseRagService

    rag_chat_id: str

    def __init__(
        self,
        config: BaseChatConversationConfig,
        rag_service: BaseRagService,
        rag_chat_id: str,
    ) -> None:
        super().__init__(config, "RAG")
        self.rag_service = rag_service
        self.rag_chat_id = rag_chat_id

    def _call_ai_chat(
        self, user_message: ChatUserMessageText
    ) -> Generator[ChatMessage, None, None]:
        """Handle user message and call AI chat service.

        Calls the RAG app service to get a streaming response and processes it.
        During streaming, stores the current message in current_response_message
        and yields it on each update.
        Once the stream is over, saves the message and adds it to the conversation.

        Args:
            user_message (str): The message from the user

        Yields:
            ChatMessageText: The current message being streamed with updated content
        """

        yield user_message

        stream = self.rag_service.chat_stream(
            query=user_message.content,
            conversation_id=self._external_conversation_id,
            chat_id=self.rag_chat_id,
        )

        end_message_response: RagChatEndStreamResponse | None = None
        external_id: str | None = None

        for stream_response in stream:
            if isinstance(stream_response, RagChatStreamResponse):
                yield self.build_current_message(
                    stream_response.answer,
                    append=not stream_response.is_from_beginning,
                )
            elif isinstance(stream_response, RagChatEndStreamResponse):
                end_message_response = stream_response

        # Process the final response
        sources: list[RagChatSource] = []
        external_conversation_id: str | None = None

        if end_message_response:
            external_conversation_id = end_message_response.session_id
            if end_message_response.sources:
                sources = end_message_response.sources

            if external_conversation_id and self._conversation_id:
                self.set_conversation_external_id(external_conversation_id)

        # Close the current message and save it
        message = self.close_current_message(external_id=external_id, sources=sources)

        if message:
            yield message
