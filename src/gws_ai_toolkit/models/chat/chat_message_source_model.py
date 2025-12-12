from gws_core import BaseModelDTO, JSONField, Model
from peewee import CharField, FloatField, ForeignKeyField, ModelSelect

from gws_ai_toolkit.core.ai_toolkit_db_manager import AiToolkitDbManager
from gws_ai_toolkit.models.chat.chat_message_model import ChatMessageModel
from gws_ai_toolkit.rag.common.rag_models import RagChatSource, RagChatSourceChunk


class ChatMessageSourceModel(Model):
    """Model representing a source for a chat message.

    Based on RagChatSource class attributes:
        message: Foreign key to ChatMessage
        document_id: ID of the source document
        document_name: Name of the source document
        score: Relevance score for the source
        chunk: Single chunk data (optional)
    """

    message = ForeignKeyField(ChatMessageModel, backref="sources", on_delete="CASCADE")
    document_id: str = CharField(max_length=100)
    document_name: str = CharField(max_length=100)
    score: float = FloatField(default=0)
    chunk: dict | None = JSONField(null=True)

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

    def set_chunk(self, chunk: RagChatSourceChunk | None) -> None:
        """Set the chunk for this source.

        :param chunk: RagChatSourceChunk or None
        :type chunk: RagChatSourceChunk | None
        """
        self.chunk = chunk.to_json_dict() if chunk else None

    def get_chunk(self) -> RagChatSourceChunk | None:
        """Get the chunk for this source.

        :return: RagChatSourceChunk or None
        :rtype: RagChatSourceChunk | None
        """
        return RagChatSourceChunk.from_json(self.chunk) if self.chunk else None

    def to_dto(self) -> BaseModelDTO:
        return self.to_rag_dto()

    def to_rag_dto(self) -> RagChatSource:
        return RagChatSource(
            id=str(self.id),
            document_id=self.document_id,
            document_name=self.document_name,
            score=self.score,
            chunk=self.get_chunk(),
        )
