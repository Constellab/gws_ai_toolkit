

from gws_ai_toolkit.core.ai_toolkit_db_manager import AiToolkitDbManager
from gws_ai_toolkit.models.chat.chat_app_dto import ChatAppDTO
from gws_core import Model
from peewee import CharField


class ChatApp(Model):
    """Model representing a chat application.

    Attributes:
        name: Unique name identifier for the chat application
    """

    name: str = CharField(unique=True)

    def to_dto(self) -> ChatAppDTO:
        """Convert model to DTO.

        :return: ChatAppDTO representation of the model
        :rtype: ChatAppDTO
        """
        return ChatAppDTO(
            id=self.id,
            name=self.name,
            created_at=self.created_at,
            last_modified_at=self.last_modified_at
        )

    class Meta:
        table_name = 'gws_ai_toolkit_chat_app'
        database = AiToolkitDbManager.get_instance().db
        is_table = True
        db_manager = AiToolkitDbManager.get_instance()
