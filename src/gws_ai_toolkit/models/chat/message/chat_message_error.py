from typing import TYPE_CHECKING, Literal

from gws_ai_toolkit.models.chat.message.chat_message_base import ChatMessageBase

if TYPE_CHECKING:
    from gws_ai_toolkit.models.chat.chat_conversation import ChatConversation
    from gws_ai_toolkit.models.chat.chat_message_model import ChatMessageModel


@ChatMessageBase.register_message_type
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

    message_type: str = "error"
    role: Literal["assistant"] = "assistant"
    error: str = ""

    def fill_from_model(self, chat_message: "ChatMessageModel") -> None:
        """Fill additional fields from the ChatMessageModel.
        This is called after the initial creation in from_chat_message_model.
        """
        self.error = chat_message.message or ""

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
            type_=self.message_type,
            content=self.error,
            external_id=self.external_id,
        )
