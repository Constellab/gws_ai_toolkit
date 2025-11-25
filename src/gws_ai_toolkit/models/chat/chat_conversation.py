

import os

from gws_ai_toolkit.core.ai_toolkit_db_manager import AiToolkitDbManager
from gws_ai_toolkit.models.chat.chat_app import ChatApp
from gws_ai_toolkit.models.chat.chat_conversation_dto import \
    ChatConversationDTO
from gws_ai_toolkit.models.user.user import User
from gws_core import BrickService, JSONField, Model
from peewee import CharField, ForeignKeyField, ModelSelect


class ChatConversation(Model):
    """Model representing a chat conversation.

    Based on ConversationHistory class attributes:
        chat_app: Foreign key to ChatApp
        conversation_id: Unique identifier for the conversation
        configuration: JSON configuration object
        mode: Mode of the conversation (RAG, AIExpert, AITable...)
        label: Label/title for the conversation
        external_conversation_id: Optional ID from external system (openai, dify, ragflow...)
    """

    chat_app: ChatApp = ForeignKeyField(ChatApp, backref='+', on_delete='CASCADE')
    configuration: dict = JSONField()
    mode: str = CharField()
    label: str = CharField(default="")
    external_conversation_id: str | None = CharField(null=True)
    user: User = ForeignKeyField(User, backref='+')

    HISTORY_EXTENSION_FOLDER_NAME = "chat_conversations"

    class Meta:
        table_name = 'gws_ai_toolkit_chat_conversation'
        database = AiToolkitDbManager.get_instance().db
        is_table = True
        db_manager = AiToolkitDbManager.get_instance()

    @classmethod
    def get_by_chat_app(cls, chat_app_id: str) -> ModelSelect:
        """Get conversations by chat app ID, ordered by last modified date (most recent first).

        :param chat_app_id: The ID of the chat app
        :type chat_app_id: str
        :return: ModelSelect query for conversations
        :rtype: ModelSelect
        """
        return (cls
                .select()
                .where(cls.chat_app == chat_app_id)
                .order_by(cls.last_modified_at.desc()))

    def to_dto(self) -> 'ChatConversationDTO':
        """Convert the ChatConversation model to a ConversationHistory DTO."""

        return ChatConversationDTO(
            id=self.id,
            chat_app_id=self.chat_app.id,
            configuration=self.configuration,
            mode=self.mode,
            label=self.label,
            external_conversation_id=self.external_conversation_id,
            created_at=self.created_at,
            last_modified_at=self.last_modified_at
        )

    def get_conversation_folder_path(self) -> str:
        """Get the folder path for storing conversation-related files.

        :return: The folder path as a string
        :rtype: str
        """

        return BrickService.get_brick_extension_dir(
            'gws_ai_toolkit',
            os.path.join(self.HISTORY_EXTENSION_FOLDER_NAME, self.id)
        )
