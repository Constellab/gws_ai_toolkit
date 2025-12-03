from typing import TYPE_CHECKING, Literal

from gws_core import BaseModelDTO, Table

from gws_ai_toolkit.models.chat.message.chat_message_base import ChatMessageBase
from gws_ai_toolkit.models.chat.message.chat_user_message import ChatUserMessageBase

if TYPE_CHECKING:
    from gws_ai_toolkit.models.chat.chat_conversation import ChatConversation
    from gws_ai_toolkit.models.chat.chat_message_model import ChatMessageModel


class ChatUserTable(BaseModelDTO):
    table_id: str
    name: str
    resource_model_id: str | None = None


class ChatUserMessageTable(ChatUserMessageBase):
    """Chat message containing text content from user.

    Specialized chat message for text-based content from users, ensuring proper typing
    and validation for text messages. This is the most common message type
    in chat conversations.

    Attributes:
        type: Fixed as "text" to identify this as a text message
        content (str): The text content of the message

    Example:
        text_msg = ChatUserMessageTable(
            role="user",
            content="What is the weather today?",
            id="msg_text_123"
        )
    """

    type: Literal["user-table"] = "user-table"

    tables: dict[str, Table]

    def fill_from_model(self, chat_message: "ChatMessageModel") -> None:
        """Fill additional fields from the ChatMessageModel.
        This is called after the initial creation in from_chat_message_model.
        """
        super().fill_from_model(chat_message)
        # TODO to define
        # self.tables = ChatUserTable.from_json_list(chat_message.data.get("tables", []))

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
            # TODO TO define
            # data={"tables": ChatUserTable.to_json_list(self.tables)},
        )

    def to_front_dto(self) -> ChatMessageBase:
        tables: list[ChatUserTable] = []
        for key, table in self.tables.items():
            tables.append(
                ChatUserTable(
                    table_id=table.uid,
                    name=key,
                    resource_model_id=table.get_model_id(),
                )
            )
        return ChatUserMessageTableFront(
            role=self.role,
            content=self.content,
            id=self.id,
            tables=tables,
            external_id=self.external_id,
        )

    class Config:
        arbitrary_types_allowed = True


class ChatUserMessageTableFront(ChatUserMessageBase):
    type: Literal["user-table-front"] = "user-table-front"

    tables: list[ChatUserTable]
