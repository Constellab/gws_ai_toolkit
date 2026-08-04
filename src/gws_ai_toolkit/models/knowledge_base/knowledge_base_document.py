"""The ``KnowledgeBaseDocument`` row — and the two invariants that make it trustworthy.

**The row id is the ``document_id`` carried by every chunk of this document in LanceDB.** Nothing
translates between the two, which is what lets a delete, a re-index and a retrieval filter all name
the same document.

**Snapshot-on-add.** ``snapshot_path`` is set when the document is added and indexing reads *only*
that. Indexing never contacts the source system, so a deleted resource or an unavailable app breaks
neither retrieval nor re-indexing. The accepted costs are bounded storage duplication and staleness
until an explicit refresh.

**Indexing lease.** Indexing runs in a Reflex background event whose process is killed on idle, so
without a lease an interrupted run would leave a row ``indexing`` forever: a permanent spinner and
ambiguous re-index semantics. ``indexing_started_at`` is stamped whenever the status is set to
``indexing``; a row whose lease is older than
:data:`DEFAULT_INDEXING_LEASE_TIMEOUT_SECONDS` is *reported* as ``error`` ("interrupted, retry") and
can be reclaimed. Re-indexing deletes the document's chunks first, so reclaiming is always safe.
"""

from datetime import datetime, timedelta

from gws_core import (
    DateHelper,
    Model,
    NullableDateTimeUTC,
    NullableJSONField,
)
from peewee import BigIntegerField, CharField, ForeignKeyField, IntegerField, ModelSelect, TextField

from gws_ai_toolkit.core.ai_toolkit_db_manager import AiToolkitDbManager
from gws_ai_toolkit.models.knowledge_base.knowledge_base import KnowledgeBase
from gws_ai_toolkit.models.knowledge_base.knowledge_base_dto import (
    DocumentIndexStatus,
    KnowledgeBaseDocumentDTO,
)

# How long a document may stay ``indexing`` before the run is presumed dead. Generous, because a
# large PDF against a hosted embedding is legitimately slow; still short enough that a killed app
# process does not leave a document stuck for a working day.
DEFAULT_INDEXING_LEASE_TIMEOUT_SECONDS = 30 * 60

INTERRUPTED_INDEXING_MESSAGE = "Indexing was interrupted, retry."


class KnowledgeBaseDocument(Model):
    """One document of one knowledge base, and everything known about its indexing."""

    knowledge_base: KnowledgeBase = ForeignKeyField(
        KnowledgeBase, backref="documents", on_delete="CASCADE"
    )
    # Open provider key, not an enum: other bricks register their own sources at load time.
    source_type: str = CharField(max_length=50)
    source_id: str | None = CharField(max_length=100, null=True)
    source_metadata: dict | None = NullableJSONField()
    # Content hash at snapshot time, so a save that changed nothing does not re-embed anything.
    source_version: str | None = CharField(max_length=100, null=True)
    # Always set. Indexing reads this and nothing else.
    snapshot_path: str = CharField(max_length=512)
    filename: str = CharField(max_length=255)
    size: int = BigIntegerField(default=0)
    index_status: str = CharField(max_length=20, default=DocumentIndexStatus.PENDING.value)
    indexing_started_at: datetime | None = NullableDateTimeUTC()
    error_message: str | None = TextField(null=True)
    chunk_count: int = IntegerField(default=0)
    indexed_at: datetime | None = NullableDateTimeUTC()

    class Meta:
        table_name = "gws_ai_toolkit_knowledge_base_document"
        database = AiToolkitDbManager.get_instance().db
        is_table = True
        db_manager = AiToolkitDbManager.get_instance()

    ############################################### QUERIES ###############################################

    @classmethod
    def get_by_knowledge_base(cls, knowledge_base_id: str) -> ModelSelect:
        """Every document of a knowledge base, newest first."""
        return (
            cls.select()
            .where(cls.knowledge_base == knowledge_base_id)
            .order_by(cls.created_at.desc())
        )

    @classmethod
    def get_by_status(
        cls, knowledge_base_id: str, index_status: DocumentIndexStatus
    ) -> ModelSelect:
        """Documents of a knowledge base in one indexing status (the ``pending`` work list)."""
        return cls.select().where(
            (cls.knowledge_base == knowledge_base_id) & (cls.index_status == index_status.value)
        )

    @classmethod
    def get_with_stale_lease(
        cls, lease_timeout_seconds: int = DEFAULT_INDEXING_LEASE_TIMEOUT_SECONDS
    ) -> ModelSelect:
        """Documents whose indexing run is presumed dead, across every knowledge base.

        A row that is ``indexing`` with no lease at all counts as stale: nothing proves it is alive,
        and leaving it alone is the permanent spinner the lease exists to prevent.
        """
        deadline = DateHelper.now_utc() - timedelta(seconds=lease_timeout_seconds)
        return cls.select().where(
            (cls.index_status == DocumentIndexStatus.INDEXING.value)
            & (cls.indexing_started_at.is_null(True) | (cls.indexing_started_at < deadline))
        )

    ############################################### LEASE ###############################################

    def has_stale_lease(
        self, lease_timeout_seconds: int = DEFAULT_INDEXING_LEASE_TIMEOUT_SECONDS
    ) -> bool:
        """True when this document is ``indexing`` but its run is presumed dead."""
        if self.index_status != DocumentIndexStatus.INDEXING.value:
            return False
        if self.indexing_started_at is None:
            return True
        age = DateHelper.now_utc() - self.indexing_started_at
        return age.total_seconds() > lease_timeout_seconds

    def get_reported_status(
        self, lease_timeout_seconds: int = DEFAULT_INDEXING_LEASE_TIMEOUT_SECONDS
    ) -> DocumentIndexStatus:
        """The status to show a user, which turns an expired lease into an honest ``error``."""
        if self.has_stale_lease(lease_timeout_seconds):
            return DocumentIndexStatus.ERROR
        return DocumentIndexStatus(self.index_status)

    ############################################### DTO ###############################################

    def to_dto(
        self, lease_timeout_seconds: int = DEFAULT_INDEXING_LEASE_TIMEOUT_SECONDS
    ) -> KnowledgeBaseDocumentDTO:
        """Convert to the DTO handed to Reflex states and HTTP responses.

        The reported status and message account for an expired lease, so a UI needs no lease logic
        of its own — and shows "interrupted, retry" whether or not a reclaim has run yet.
        """
        stale = self.has_stale_lease(lease_timeout_seconds)
        return KnowledgeBaseDocumentDTO(
            id=self.id,
            # Read straight off the foreign-key column: resolving the relation would cost a query
            # per document in a list.
            knowledge_base_id=self.knowledge_base_id,
            source_type=self.source_type,
            source_id=self.source_id,
            source_metadata=self.source_metadata,
            source_version=self.source_version,
            filename=self.filename,
            size=self.size,
            index_status=self.get_reported_status(lease_timeout_seconds).value,
            error_message=INTERRUPTED_INDEXING_MESSAGE if stale else self.error_message,
            chunk_count=self.chunk_count,
            indexed_at=self.indexed_at,
            created_at=self.created_at,
            last_modified_at=self.last_modified_at,
        )
