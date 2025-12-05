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
    code: str = ""

    def fill_from_model(self, chat_message: "ChatMessageModel") -> None:
        """Fill additional fields from the ChatMessageModel.
        This is called after the initial creation in from_chat_message_model.
        """
        self.code = chat_message.data.get("code", "")

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
