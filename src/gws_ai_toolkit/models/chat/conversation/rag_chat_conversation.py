from collections.abc import Generator

from gws_ai_toolkit.models.chat.message import AllChatMessages
from gws_ai_toolkit.rag.common.base_rag_app_service import BaseRagAppService
from gws_ai_toolkit.rag.common.rag_models import RagChatEndStreamResponse, RagChatSource, RagChatStreamResponse

from .base_chat_conversation import BaseChatConversation


class RagChatConversation(BaseChatConversation):
    """Chat conversation implementation for RAG (Retrieval Augmented Generation).

    This class handles RAG-based chat conversations with streaming support,
    storing messages during streaming and persisting them once the stream completes.
    """

    rag_app_service: BaseRagAppService

    rag_chat_id: str

    def __init__(
        self, chat_app_name: str, configuration: dict, rag_app_service: BaseRagAppService, rag_chat_id: str
    ) -> None:
        super().__init__(chat_app_name, configuration, "RAG")
        self.rag_app_service = rag_app_service
        self.rag_chat_id = rag_chat_id

    def call_ai_chat(self, user_message: str) -> Generator[AllChatMessages, None, None]:
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
        external_conversation_id = None
        if self._conversation:
            external_conversation_id = self._conversation.external_conversation_id

        stream = self.rag_app_service.send_message_stream(
            query=user_message,
            conversation_id=external_conversation_id,
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
        conversation_id: str | None = None

        if end_message_response:
            conversation_id = end_message_response.session_id
            if end_message_response.sources:
                sources = end_message_response.sources

            if conversation_id and self._conversation:
                self._conversation.external_conversation_id = conversation_id
                self._conversation.save()

        # Close the current message and save it
        message = self.close_current_message(external_id=external_id, sources=sources)

        if message:
            yield message
