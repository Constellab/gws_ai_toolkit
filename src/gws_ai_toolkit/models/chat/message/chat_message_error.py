from typing import TYPE_CHECKING, Literal

from gws_ai_toolkit.models.chat.message.chat_message_base import ChatMessageBase

if TYPE_CHECKING:
    from gws_ai_toolkit.models.chat.chat_conversation import ChatConversation
    from gws_ai_toolkit.models.chat.chat_message_model import ChatMessageModel


class ChatMessageError(ChatMessageBase):
    """Chat message representing an error.

    Specialized chat message for conveying error information within the
    chat conversation. Used to inform users about issues or problems
    encountered during interactions.

    Attributes:
        type: Fixed as "error" to identify this as an error message
        error (str): The error message content

    Example:
        error_msg = ChatMessageError(
            role="assistant",
            error="An error occurred while processing your request.",
            id="msg_error_123"
        )
    """

    type: Literal["error"] = "error"
    role: Literal["assistant"] = "assistant"
    error: str

    @classmethod
    def from_chat_message_model(cls, chat_message: "ChatMessageModel") -> "ChatMessageError":
        """Convert database ChatMessage model to ChatMessageError DTO.

        :param chat_message: The database ChatMessage instance to convert
        :type chat_message: ChatMessage
        :return: ChatMessageError DTO instance
        :rtype: ChatMessageError
        """
        sources = [source.to_rag_dto() for source in chat_message.sources]
        return cls(
            id=chat_message.id,
            external_id=chat_message.external_id,
            sources=sources,
            error=chat_message.message,
        )

    def to_chat_message_model(self, conversation: "ChatConversation") -> "ChatMessageModel":
        """Convert DTO to database ChatMessage model.

        :param conversation: The conversation this message belongs to
        :type conversation: ChatConversation
        :return: ChatMessage database model instance
        :rtype: ChatMessage
        """
        from gws_ai_toolkit.models.chat.chat_message_model import ChatMessageModel

        return ChatMessageModel.build_message(
            conversation=conversation,
            role=self.role,
            type_=self.type,
            content=self.error,
            external_id=self.external_id,
        )
