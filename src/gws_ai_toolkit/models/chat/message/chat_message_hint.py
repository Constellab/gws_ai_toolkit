from typing import TYPE_CHECKING, Literal

from gws_ai_toolkit.models.chat.message.chat_message_base import ChatMessageBase

if TYPE_CHECKING:
    from gws_ai_toolkit.models.chat.chat_conversation import ChatConversation
    from gws_ai_toolkit.models.chat.chat_message_model import ChatMessageModel


class ChatMessageHint(ChatMessageBase):
    """Chat message containing hint content.

    Specialized chat message for providing hints, tips, or helpful suggestions
    to users during their chat conversation. Used to offer guidance or provide
    contextual information without being a direct response.

    Attributes:
        type: Fixed as "hint" to identify this as a hint message
        content (str): The hint message content

    Example:
        hint_msg = ChatMessageHint(
            role="assistant",
            content="Try asking about specific topics for better results.",
            id="msg_hint_123"
        )
    """

    type: Literal["hint"] = "hint"
    role: Literal["assistant"] = "assistant"
    content: str

    @classmethod
    def from_chat_message_model(cls, chat_message: "ChatMessageModel") -> "ChatMessageHint":
        """Convert database ChatMessage model to ChatMessageHint DTO.

        :param chat_message: The database ChatMessage instance to convert
        :type chat_message: ChatMessage
        :return: ChatMessageHint DTO instance
        :rtype: ChatMessageHint
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
        from gws_ai_toolkit.models.chat.chat_message_model import ChatMessageModel

        return ChatMessageModel.build_message(
            conversation=conversation,
            role=self.role,
            type_=self.type,
            content=self.content,
            external_id=self.external_id,
        )
