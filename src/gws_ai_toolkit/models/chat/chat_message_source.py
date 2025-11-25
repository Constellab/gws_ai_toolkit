from gws_core import JSONField, Model
from peewee import CharField, FloatField, ForeignKeyField, ModelSelect

from gws_ai_toolkit.core.ai_toolkit_db_manager import AiToolkitDbManager
from gws_ai_toolkit.models.chat.chat_message_model import ChatMessageModel
from gws_ai_toolkit.rag.common.rag_models import RagChatSource, RagChatSourceChunk


class ChatMessageSource(Model):
    """Model representing a source for a chat message.

    Based on RagChatSource class attributes:
        message: Foreign key to ChatMessage
        document_id: ID of the source document
        document_name: Name of the source document
        score: Relevance score for the source
    """

    message = ForeignKeyField(ChatMessageModel, backref="sources", on_delete="CASCADE")
    document_id: str = CharField()
    document_name: str = CharField()
    score: float = FloatField(default=0)
    chunks: list = JSONField()

    class Meta:
        table_name = "gws_ai_toolkit_chat_message_source"
        database = AiToolkitDbManager.get_instance().db
        is_table = True
        db_manager = AiToolkitDbManager.get_instance()

    @classmethod
    def get_by_message(cls, message_id: str) -> ModelSelect:
        """Get sources by message ID.

        :param message_id: The ID of the message
        :type message_id: str
        :return: ModelSelect query for sources
        :rtype: ModelSelect
        """
        return cls.select().where(cls.message == message_id)

    def set_chunks(self, chunks: list[RagChatSourceChunk]) -> None:
        """Set the chunks for this source.

        :param chunks: List of RagChatSourceChunk
        :type chunks: list[RagChatSourceChunk]
        """
        self.chunks = [chunk.to_json_dict() for chunk in chunks]

    def get_chunks(self) -> list[RagChatSourceChunk]:
        """Get the chunks for this source.

        :return: List of RagChatSourceChunk
        :rtype: list[RagChatSourceChunk]
        """
        return RagChatSourceChunk.from_json_list(self.chunks)

    def to_rag_dto(self) -> RagChatSource:
        return RagChatSource(
            document_id=self.document_id, document_name=self.document_name, score=self.score, chunks=self.get_chunks()
        )
