from typing import TYPE_CHECKING, Literal

from gws_ai_toolkit.models.chat.message.chat_message_base import ChatMessageBase

if TYPE_CHECKING:
    pass


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
    content: str = ""

    # def fill_from_model(self, chat_message: "ChatMessageModel") -> None:
    #     """Fill additional fields from the ChatMessageModel.
    #     This is called after the initial creation in from_chat_message_model.
    #     """
    #     self.content = chat_message.message or ""

    # def to_chat_message_model(self, conversation: "ChatConversation") -> "ChatMessageModel":
    #     """Convert DTO to database ChatMessage model.

    #     :param conversation: The conversation this message belongs to
    #     :type conversation: ChatConversation
    #     :return: ChatMessage database model instance
    #     :rtype: ChatMessage
    #     """
    #     # Import at runtime to avoid circular imports
    #     # This is necessary since ChatMessage also imports from this module
    #     from gws_ai_toolkit.models.chat.chat_message_model import ChatMessageModel

    #     return ChatMessageModel.build_message(
    #         conversation=conversation,
    #         role=self.role,
    #         type_=self.type,
    #         content=self.content,
    #         external_id=self.external_id,
    #     )
