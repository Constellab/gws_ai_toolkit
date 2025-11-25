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
    content: str = ""

    def fill_from_model(self, chat_message: "ChatMessageModel") -> None:
        """Fill additional fields from the ChatMessageModel.
        This is called after the initial creation in from_chat_message_model.
        """
        self.content = chat_message.message or ""

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
