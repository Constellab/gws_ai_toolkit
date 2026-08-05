from typing import TYPE_CHECKING, Literal

from gws_ai_toolkit.models.chat.message.chat_message_base import ChatMessageBase

if TYPE_CHECKING:
    from gws_ai_toolkit.models.chat.chat_conversation import ChatConversation
    from gws_ai_toolkit.models.chat.chat_message_model import ChatMessageModel


class ChatUserMessageBase(ChatMessageBase):
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

    role: Literal["user"] = "user"
    content: str = ""

    def fill_from_model(self, chat_message: "ChatMessageModel") -> None:
        """Fill additional fields from the ChatMessageModel.
        This is called after the initial creation in from_chat_message_model.
        """
        self.content = chat_message.message or ""


@ChatMessageBase.register_message_type
class ChatUserMessageText(ChatUserMessageBase):
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

    message_type: str = "user-text"

    # Document Focus (issue #29): narrows KnowledgeBaseAgentAi's search_knowledge tool to these
    # documents for this message's turn. Empty means unscoped. Rides in ChatMessageModel.data, the
    # same way tool calls/table attachments do — see ChatMessageToolCall for the pattern.
    focused_document_ids: list[str] = []

    def fill_from_model(self, chat_message: "ChatMessageModel") -> None:
        """Fill additional fields from the ChatMessageModel.
        This is called after the initial creation in from_chat_message_model.
        """
        super().fill_from_model(chat_message)
        data = chat_message.data or {}
        self.focused_document_ids = data.get("focused_document_ids") or []

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
            content=self.content,
            external_id=self.external_id,
            data={"focused_document_ids": self.focused_document_ids},
        )
