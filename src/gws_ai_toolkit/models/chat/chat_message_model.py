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

    conversation: ChatConversation = ForeignKeyField(
        ChatConversation, backref="+", on_delete="CASCADE"
    )
    role: Literal["user", "assistant"] = CharField(max_length=20)
    type: str = CharField(max_length=20)
    external_id: str | None = CharField(null=True, max_length=100)
    message: str | None = TextField(null=True)
    filename: str | None = CharField(null=True, max_length=100)
    data: dict = JSONField(null=True)
    user: User = ForeignKeyField(User, backref="+")

    sources: list["ChatMessageSourceModel"]

    # Position of the message inside its conversation, kept in `data` so no schema change is
    # needed. `created_at` is a DATETIME with second precision, so the several messages of one
    # turn — a user prompt, a tool call, its result, the answer — routinely share a timestamp
    # and their relative order would otherwise be whatever the database happens to return. That
    # order is what a restored message history replays, so it is recorded rather than assumed.
    SEQUENCE_DATA_KEY = "_seq"

    class Meta:
        table_name = "gws_ai_toolkit_chat_message"
        database = AiToolkitDbManager.get_instance().db
        is_table = True
        db_manager = AiToolkitDbManager.get_instance()

    @classmethod
    def get_by_conversation(cls, conversation_id: str) -> list["ChatMessageModel"]:
        """Get messages by conversation ID, ordered by creation date (oldest first).

        Messages sharing a `created_at` second are ordered by their recorded position, so the
        messages of a single turn always come back in the order they were saved.

        :param conversation_id: The ID of the conversation
        :type conversation_id: str
        :return: The conversation's messages, oldest first
        :rtype: List[ChatMessage]
        """
        messages = list(
            cls.select().where(cls.conversation == conversation_id).order_by(cls.created_at.asc())
        )
        return sorted(messages, key=lambda message: (message.created_at, message.get_sequence()))

    def get_sequence(self) -> int:
        """Get the position of this message inside its conversation.

        :return: The recorded position, or 0 for a message saved before positions were recorded
        :rtype: int
        """
        return (self.data or {}).get(self.SEQUENCE_DATA_KEY, 0)

    def set_next_sequence(self) -> None:
        """Record this message's position as the next one in its conversation.

        Called just before saving. Messages of one conversation are saved one at a time, so
        counting the rows already there yields a monotonic position.
        """
        already_saved = (
            ChatMessageModel.select()
            .where(ChatMessageModel.conversation == self.conversation)
            .count()
        )

        data = dict(self.data or {})
        data[self.SEQUENCE_DATA_KEY] = already_saved
        self.data = data

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
