from typing import TYPE_CHECKING, Literal

from gws_ai_toolkit.models.chat.message.chat_message_base import ChatMessageBase

if TYPE_CHECKING:
    from gws_ai_toolkit.models.chat.chat_conversation import ChatConversation
    from gws_ai_toolkit.models.chat.chat_message_model import ChatMessageModel


class ChatMessageText(ChatMessageBase):
    """Chat message containing text content from assistant.

    Specialized chat message for text-based content, ensuring proper typing
    and validation for text messages. This is the most common message type
    in chat conversations.

    Attributes:
        type: Fixed as "text" to identify this as a text message
        content (str): The text content of the message

    Example:
        text_msg = ChatMessageText(
            role="assistant",
            content="Here is the answer to your question.",
            id="msg_text_123"
        )
    """

    type: Literal["text"] = "text"
    role: Literal["assistant"] = "assistant"
    content: str

    @classmethod
    def from_chat_message_model(cls, chat_message: "ChatMessageModel") -> "ChatMessageText":
        """Convert database ChatMessage model to ChatMessageText DTO.

        :param chat_message: The database ChatMessage instance to convert
        :type chat_message: ChatMessage
        :return: ChatMessageText DTO instance
        :rtype: ChatMessageText
        """
        sources = [source.to_rag_dto() for source in chat_message.sources]
        return cls(
            id=chat_message.id,
            external_id=chat_message.external_id,
            sources=sources,
            content=chat_message.message,
        )

    def to_chat_message_model(self, conversation: "ChatConversation") -> "ChatMessageModel":
        """Convert DTO to database ChatMessage model.

        :param conversation: The conversation this message belongs to
        :type conversation: ChatConversation
        :return: ChatMessage database model instance
        :rtype: ChatMessage
        """
        # Import at runtime to avoid circular imports
        # This is necessary since ChatMessage also imports from this module
        from gws_ai_toolkit.models.chat.chat_message_model import ChatMessageModel

        return ChatMessageModel.build_message(
            conversation=conversation,
            role=self.role,
            type_=self.type,
            content=self.content,
            external_id=self.external_id,
        )


class ChatUserMessageText(ChatMessageBase):
    """Chat message containing text content from user.

    Specialized chat message for text-based content from users, ensuring proper typing
    and validation for text messages. This is the most common message type
    in chat conversations.

    Attributes:
        type: Fixed as "text" to identify this as a text message
        content (str): The text content of the message

    Example:
        text_msg = ChatUserMessageText(
            role="user",
            content="What is the weather today?",
            id="msg_text_123"
        )
    """

    type: Literal["text"] = "text"
    role: Literal["user"] = "user"
    content: str

    @classmethod
    def from_chat_message_model(cls, chat_message: "ChatMessageModel") -> "ChatUserMessageText":
        """Convert database ChatMessage model to ChatUserMessageText DTO.

        :param chat_message: The database ChatMessage instance to convert
        :type chat_message: ChatMessage
        :return: ChatUserMessageText DTO instance
        :rtype: ChatUserMessageText
        """
        return cls(
            id=chat_message.id,
            content=chat_message.message,
            external_id=chat_message.external_id,
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
            content=self.content,
            external_id=self.external_id,
        )
