"""The ``KnowledgeBase`` row: a named, persisted collection of indexed documents."""

from gws_core import Model, NullableJSONField
from peewee import CharField, IntegerField, ModelSelect, TextField

from gws_ai_toolkit.core.ai_toolkit_db_manager import AiToolkitDbManager
from gws_ai_toolkit.models.knowledge_base.knowledge_base_dto import KnowledgeBaseDTO
from gws_ai_toolkit.rag.knowledge_base.knowledge_base_config import (
    DEFAULT_CHUNK_OVERLAP,
    DEFAULT_CHUNK_SIZE,
    ChunkConfig,
)
from gws_ai_toolkit.rag.knowledge_base.knowledge_base_storage import DEFAULT_INSTANCE_SCOPE


class KnowledgeBase(Model):
    """A knowledge base: a name, a chunking policy, and the engine instance holding its chunks.

    ``instance_scope`` decides *which* LanceDB directory the chunks live in, and is therefore the
    one property that cannot be edited freely once documents are indexed: moving a knowledge base to
    another scope means re-indexing it, because scoping is structural rather than a filter. Chunk
    size and overlap, by contrast, only affect documents indexed after the change.

    Embedding configuration is **not** here: it is a property of the instance, shared by every
    knowledge base in it (see ``rag/knowledge_base/embedding_manifest.py``).
    """

    name: str = CharField(max_length=100, unique=True)
    description: str = TextField(default="")
    instance_scope: str = CharField(max_length=50, default=DEFAULT_INSTANCE_SCOPE)
    chunk_size: int = IntegerField(default=DEFAULT_CHUNK_SIZE)
    chunk_overlap: int = IntegerField(default=DEFAULT_CHUNK_OVERLAP)
    # Provider used for bulk sync; null means this knowledge base is only filled by hand.
    sync_source_type: str | None = CharField(max_length=50, null=True)
    sync_config: dict | None = NullableJSONField()

    class Meta:
        table_name = "gws_ai_toolkit_knowledge_base"
        database = AiToolkitDbManager.get_instance().db
        is_table = True
        db_manager = AiToolkitDbManager.get_instance()

    @classmethod
    def get_by_name(cls, name: str) -> "KnowledgeBase | None":
        """The knowledge base with this name, or None."""
        return cls.get_or_none(cls.name == name)

    @classmethod
    def get_all_ordered_by_name(cls) -> ModelSelect:
        """Every knowledge base, in a stable order for a UI list."""
        return cls.select().order_by(cls.name)

    def get_chunk_config(self) -> ChunkConfig:
        """The chunking configuration the engine indexes this knowledge base's documents with."""
        return ChunkConfig(chunk_size=self.chunk_size, chunk_overlap=self.chunk_overlap)

    def to_dto(self) -> KnowledgeBaseDTO:
        """Convert to the DTO handed to Reflex states and HTTP responses."""
        return KnowledgeBaseDTO(
            id=self.id,
            name=self.name,
            description=self.description,
            instance_scope=self.instance_scope,
            chunk_size=self.chunk_size,
            chunk_overlap=self.chunk_overlap,
            sync_source_type=self.sync_source_type,
            sync_config=self.sync_config,
            created_at=self.created_at,
            last_modified_at=self.last_modified_at,
        )
