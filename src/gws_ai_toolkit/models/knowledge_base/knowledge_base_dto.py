"""DTOs of the knowledge-base persistence layer.

Reflex states are handed these, never Peewee rows: a row carries a live database connection, lazy
foreign keys and no serialisation contract, and a Reflex state is serialised across the wire on
every event. The boundary is not decorative.

``snapshot_path`` is deliberately absent from :class:`KnowledgeBaseDocumentDTO`. It is a server-side
path, and a Reflex state is serialised to the browser: code that needs the file reads
``KnowledgeBaseDocument.snapshot_path`` off the row, on the server, where it means something.
"""

from datetime import datetime
from enum import Enum

from gws_core import BaseModelDTO, ModelDTO

from gws_ai_toolkit.rag.knowledge_base.knowledge_base_config import (
    DEFAULT_CHUNK_OVERLAP,
    DEFAULT_CHUNK_SIZE,
)
from gws_ai_toolkit.rag.knowledge_base.knowledge_base_storage import DEFAULT_INSTANCE_SCOPE


class DocumentIndexStatus(str, Enum):
    """Where a document stands in the indexing pipeline.

    ``INDEXING`` is a leased state, not a resting one: see
    :meth:`~.knowledge_base_document.KnowledgeBaseDocument.has_stale_lease`.
    """

    PENDING = "pending"
    INDEXING = "indexing"
    DONE = "done"
    ERROR = "error"


class KnowledgeBaseDTO(ModelDTO):
    """A knowledge base as the UI and the HTTP layer see it."""

    name: str
    description: str
    instance_scope: str
    chunk_size: int
    chunk_overlap: int
    sync_source_type: str | None = None
    sync_config: dict | None = None


class SaveKnowledgeBaseDTO(BaseModelDTO):
    """Input of a knowledge-base create or update."""

    name: str
    description: str = ""
    instance_scope: str = DEFAULT_INSTANCE_SCOPE
    chunk_size: int = DEFAULT_CHUNK_SIZE
    chunk_overlap: int = DEFAULT_CHUNK_OVERLAP
    sync_source_type: str | None = None
    sync_config: dict | None = None


class KnowledgeBaseDocumentDTO(ModelDTO):
    """A document as the UI and the HTTP layer see it.

    ``index_status`` and ``error_message`` are the *reported* status: a document whose indexing lease
    has expired reads as ``error`` here even before anything has reclaimed it, because a permanent
    spinner is worse than an honest "interrupted, retry".
    """

    knowledge_base_id: str
    source_type: str
    source_id: str | None = None
    source_metadata: dict | None = None
    source_version: str | None = None
    filename: str
    size: int
    index_status: str
    error_message: str | None = None
    chunk_count: int
    indexed_at: datetime | None = None
