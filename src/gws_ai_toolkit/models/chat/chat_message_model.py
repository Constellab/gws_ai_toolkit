import os
from typing import TYPE_CHECKING, Literal

from gws_core import JSONField, Model
from peewee import CharField, ForeignKeyField, TextField

from gws_ai_toolkit.core.ai_toolkit_db_manager import AiToolkitDbManager
from gws_ai_toolkit.models.chat.chat_conversation import ChatConversation
from gws_ai_toolkit.models.chat.message.chat_message_base import ChatMessageBase
from gws_ai_toolkit.models.user.user import User

if TYPE_CHECKING:
    from gws_ai_toolkit.models.chat.chat_message_source_model import ChatMessageSourceModel


class ChatMessageModel(Model):
    """Model representing a chat message.

    Based on ChatMessageBase class attributes:
        conversation: Foreign key to ChatConversation
        role: Role of the message sender (user or assistant)
        type: Type of message (text, image, code, plotly, error, hint)
        external_id: Optional external system ID for the message
        content: Content of the message (stored as string)
        data: Additional data object stored as JSON
    """

    conversation: ChatConversation = ForeignKeyField(ChatConversation, backref="+", on_delete="CASCADE")
    role: Literal["user", "assistant"] = CharField(max_length=20)
    type: str = CharField(max_length=20)
    external_id: str | None = CharField(null=True, max_length=100)
    message: str | None = TextField(null=True)
    filename: str | None = CharField(null=True, max_length=100)
    data: dict = JSONField(null=True)
    user: User = ForeignKeyField(User, backref="+")

    sources: list["ChatMessageSourceModel"]

    class Meta:
        table_name = "gws_ai_toolkit_chat_message"
        database = AiToolkitDbManager.get_instance().db
        is_table = True
        db_manager = AiToolkitDbManager.get_instance()

    @classmethod
    def get_by_conversation(cls, conversation_id: str) -> list["ChatMessageModel"]:
        """Get messages by conversation ID, ordered by creation date (oldest first).

        :param conversation_id: The ID of the conversation
        :type conversation_id: str
        :return: ModelSelect query for messages
        :rtype: List[ChatMessage]
        """
        return list(cls.select().where(cls.conversation == conversation_id).order_by(cls.created_at.asc()))

    @classmethod
    def build_message(
        cls,
        conversation: ChatConversation,
        role: Literal["user", "assistant"],
        type_: str,
        content: str | None = None,
        external_id: str | None = None,
        data: dict | None = None,
        filename: str | None = None,
    ) -> "ChatMessageModel":
        message = cls()
        message.conversation = conversation
        message.role = role
        message.type = type_
        message.message = content
        message.external_id = external_id
        message.data = data or {}
        message.filename = filename
        return message

    def to_chat_message(self) -> ChatMessageBase:
        """Convert database ChatMessage model to ChatMessageDTO union type.

        :return: ChatMessage union type instance
        :rtype: ChatMessageDTO
        """
        from gws_ai_toolkit.models.chat.message.chat_message_base import ChatMessageBase

        return ChatMessageBase.from_chat_message_model(self)

    def get_filepath_if_exists(self) -> str | None:
        """Get the full file path for the message's filename if it exists.

        :param conversation_folder_path: The folder path of the conversation
        :type conversation_folder_path: str
        :return: Full file path if exists, else None
        :rtype: str | None
        """
        conversation_folder_path = self.conversation.get_conversation_folder_path()
        if self.filename:
            file_path = os.path.join(conversation_folder_path, self.filename)
            if os.path.exists(file_path):
                return file_path
        return None
