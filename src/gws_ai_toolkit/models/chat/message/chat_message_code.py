from typing import TYPE_CHECKING, Literal

from gws_ai_toolkit.models.chat.message.chat_message_base import ChatMessageBase

if TYPE_CHECKING:
    from gws_ai_toolkit.models.chat.chat_conversation import ChatConversation
    from gws_ai_toolkit.models.chat.chat_message_model import ChatMessageModel


class ChatMessageCode(ChatMessageBase):
    """Chat message containing code content.

    Specialized chat message for code blocks, providing proper formatting
    and syntax highlighting for programming code shared in conversations.
    Commonly used for code examples, generated scripts, or code analysis.

    Attributes:
        type: Fixed as "code" to identify this as a code message
        code (str): The code content with proper formatting

    Example:
        code_msg = ChatMessageCode(
            role="assistant",
            code="print('Hello, world!')",
            id="msg_code_123"
        )
    """

    type: Literal["code"] = "code"
    role: Literal["assistant"] = "assistant"
    code: str

    @classmethod
    def from_chat_message_model(cls, chat_message: "ChatMessageModel") -> "ChatMessageCode":
        """Convert database ChatMessage model to ChatMessageCode DTO.

        :param chat_message: The database ChatMessage instance to convert
        :type chat_message: ChatMessage
        :return: ChatMessageCode DTO instance
        :rtype: ChatMessageCode
        """
        sources = [source.to_rag_dto() for source in chat_message.sources]
        return cls(
            id=chat_message.id,
            external_id=chat_message.external_id,
            sources=sources,
            code=chat_message.data.get("code", ""),
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
            content="",
            external_id=self.external_id,
            data={"code": self.code},
        )
