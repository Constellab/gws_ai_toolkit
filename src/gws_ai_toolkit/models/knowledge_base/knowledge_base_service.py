"""The knowledge-base service: upload bytes in, an indexed document with a trustworthy status out.

It owns three things the models and the engine deliberately do not:

- **The snapshot-on-add invariant.** Every document row is created with a snapshot already written.
  Indexing then reads only that path, so a resource deleted from the lab or a brick that stopped
  answering breaks neither retrieval nor re-indexing.
- **The indexing lease.** Status transitions are stamped and committed one at a time rather than
  wrapped in a single transaction, because a lease no other process can see is not a lease. See
  :meth:`KnowledgeBaseService.index_document`.
- **Where the compatibility check runs**: on the *fetched file*, before a row exists, so every
  provider is held to the same rules — the rules themselves live in ``DocumentCompatibility``.

Every mutation runs inside a transaction, and the service talks to source systems only through
``KnowledgeBaseDocumentSourceRegistry``. Callers are handed rows, as in ``models/chat/``; the DTO
boundary for Reflex states is ``to_dto()`` on those rows.

:meth:`KnowledgeBaseService.import_documents` is the same idea applied in bulk, and it knows about no
provider in particular: anything implementing ``list_documents`` can be imported from. It is a bulk
**add**, not a subscription — nothing here deletes, and nothing is written back to the source system.
"""

import os
from typing import NamedTuple

from gws_core import BaseModelDTO, DateHelper, FileHelper, Logger, Settings

from gws_ai_toolkit.core.ai_toolkit_db_manager import AiToolkitDbManager
from gws_ai_toolkit.models.knowledge_base.embedding_manifest_model import DbEmbeddingManifestStore
from gws_ai_toolkit.models.knowledge_base.knowledge_base import KnowledgeBase
from gws_ai_toolkit.models.knowledge_base.knowledge_base_document import (
    DEFAULT_INDEXING_LEASE_TIMEOUT_SECONDS,
    INTERRUPTED_INDEXING_MESSAGE,
    KnowledgeBaseDocument,
)
from gws_ai_toolkit.models.knowledge_base.knowledge_base_dto import (
    DocumentIndexStatus,
    ImportedDocumentDTO,
    ImportReport,
    ImportSkipReason,
    SaveKnowledgeBaseDTO,
    SkippedDocumentDTO,
)
from gws_ai_toolkit.rag.knowledge_base.document_compatibility import DocumentCompatibility
from gws_ai_toolkit.rag.knowledge_base.knowledge_base_config import EmbeddingConfig
from gws_ai_toolkit.rag.knowledge_base.knowledge_base_engine import KnowledgeBaseEngine
from gws_ai_toolkit.rag.knowledge_base.knowledge_base_storage import KnowledgeBaseStorage
from gws_ai_toolkit.rag.knowledge_base.sources.knowledge_base_source import (
    DOCUMENT_REJECTION_ERRORS,
    KnowledgeBaseDocumentSourceRegistry,
    SourceDocumentCandidate,
    SourceOpenAction,
    compute_bytes_content_hash,
    compute_file_content_hash,
)
from gws_ai_toolkit.rag.knowledge_base.sources.upload_source import UPLOAD_SOURCE_TYPE


class KnowledgeBaseNameAlreadyUsedError(Exception):
    """Raised when a knowledge-base name is already taken."""


class DocumentSnapshot(BaseModelDTO):
    """A snapshot that has just been written, and the two facts derived from it.

    These three travel together from the moment a file is admitted to the moment a row records it,
    on both the add and the refresh path — so they are one value rather than three parameters.
    """

    snapshot_path: str
    size: int
    source_version: str


class DocumentRefresh(NamedTuple):
    """What a refresh found: the document row, and whether its content actually changed.

    ``content_changed`` is what makes a refresh cheap. The version marker is a content hash, so a
    save that changed nothing produces the same hash — and a caller that re-indexes unconditionally
    would pay for embedding an identical document. The flag is returned rather than inferred from the
    row because the row cannot tell the two cases apart afterwards.
    """

    document: KnowledgeBaseDocument
    content_changed: bool


class KnowledgeBaseService:
    """Creates knowledge bases, gets documents into them, and keeps their status honest."""

    ############################################### ENGINE ###############################################

    @classmethod
    def build_engine(
        cls, instance_scope: str, embedding_config: EmbeddingConfig
    ) -> KnowledgeBaseEngine:
        """The engine for one instance scope, with its manifest held in the database.

        The engine's own default keeps the manifest in a file next to the vectors; once there is a
        database the manifest belongs in it, keyed by scope.
        """
        return KnowledgeBaseEngine.from_scope(
            embedding_config=embedding_config,
            instance_scope=instance_scope,
            manifest_store=DbEmbeddingManifestStore(),
        )

    ############################################### KNOWLEDGE BASE CRUD ###############################################

    def get_knowledge_base(self, knowledge_base_id: str) -> KnowledgeBase | None:
        """The knowledge base with this id, or None."""
        return KnowledgeBase.get_by_id(knowledge_base_id)

    def get_knowledge_base_and_check(self, knowledge_base_id: str) -> KnowledgeBase:
        """The knowledge base with this id.

        :raises NotFoundException: if there is none
        """
        return KnowledgeBase.get_by_id_and_check(knowledge_base_id)

    def get_all_knowledge_bases(self) -> list[KnowledgeBase]:
        """Every knowledge base, ordered by name."""
        return list(KnowledgeBase.get_all_ordered_by_name())

    @AiToolkitDbManager.transaction()
    def create_knowledge_base(self, knowledge_base_dto: SaveKnowledgeBaseDTO) -> KnowledgeBase:
        """Create a knowledge base.

        :raises KnowledgeBaseNameAlreadyUsedError: if the name is taken — checked here so callers
                get a message instead of a database integrity error
        """
        self._check_name_is_free(knowledge_base_dto.name)

        knowledge_base = KnowledgeBase()
        self._apply_knowledge_base_dto(knowledge_base, knowledge_base_dto)
        knowledge_base.save()
        return knowledge_base

    @AiToolkitDbManager.transaction()
    def update_knowledge_base(
        self, knowledge_base_id: str, knowledge_base_dto: SaveKnowledgeBaseDTO
    ) -> KnowledgeBase:
        """Update a knowledge base.

        ``instance_scope`` is updated like any other field, but moving a populated knowledge base to
        another scope leaves its chunks behind in the old instance: scoping is structural, so the
        documents must be re-indexed. Callers that expose this should say so.

        :raises NotFoundException: if the knowledge base does not exist
        :raises KnowledgeBaseNameAlreadyUsedError: if the new name belongs to another knowledge base
        """
        knowledge_base = self.get_knowledge_base_and_check(knowledge_base_id)
        self._check_name_is_free(knowledge_base_dto.name, allowed_id=knowledge_base.id)

        self._apply_knowledge_base_dto(knowledge_base, knowledge_base_dto)
        knowledge_base.save()
        return knowledge_base

    def delete_knowledge_base(self, knowledge_base_id: str, engine: KnowledgeBaseEngine) -> None:
        """Delete a knowledge base: its chunks, its snapshots, its document rows and its own row.

        The chunks go first. A failure there leaves everything else in place, so the delete can be
        retried; the reverse order would leave orphaned chunks that nothing points at any more and
        that a retrieval could still return.

        :raises NotFoundException: if the knowledge base does not exist
        """
        knowledge_base = self.get_knowledge_base_and_check(knowledge_base_id)

        engine.delete_knowledge_base(knowledge_base.id)
        files_dir = KnowledgeBaseStorage.get_files_dir(knowledge_base.id)

        self._delete_knowledge_base_rows(knowledge_base)
        FileHelper.delete_dir(files_dir)

    ############################################### DOCUMENTS: READ ###############################################

    def get_document(self, document_id: str) -> KnowledgeBaseDocument | None:
        """The document with this id, or None."""
        return KnowledgeBaseDocument.get_by_id(document_id)

    def get_document_and_check(self, document_id: str) -> KnowledgeBaseDocument:
        """The document with this id.

        :raises NotFoundException: if there is none
        """
        return KnowledgeBaseDocument.get_by_id_and_check(document_id)

    def get_documents(self, knowledge_base_id: str) -> list[KnowledgeBaseDocument]:
        """Every document of a knowledge base, newest first."""
        return list(KnowledgeBaseDocument.get_by_knowledge_base(knowledge_base_id))

    def get_documents_to_index(self, knowledge_base_id: str) -> list[KnowledgeBaseDocument]:
        """The documents of a knowledge base still waiting to be indexed."""
        return list(
            KnowledgeBaseDocument.get_by_status(knowledge_base_id, DocumentIndexStatus.PENDING)
        )

    def get_document_open_action(self, document: KnowledgeBaseDocument) -> SourceOpenAction | None:
        """How the UI should open this document, as its own provider decides.

        Falls back to downloading the snapshot when the provider is not registered — a document
        whose brick was uninstalled is still readable, because the snapshot is always there.
        """
        source = KnowledgeBaseDocumentSourceRegistry.get_or_none(document.source_type)
        if source is None:
            return SourceOpenAction.download_snapshot()
        return source.get_open_action(document.to_dto())

    ############################################### DOCUMENTS: ADD ###############################################

    def add_uploaded_document(
        self, knowledge_base_id: str, filename: str, content: bytes
    ) -> KnowledgeBaseDocument:
        """Add a document from uploaded bytes. Those bytes *are* the snapshot.

        The row lands as ``pending``: adding a document and indexing it are separate steps, so an
        upload never blocks on an embedding call.

        :param knowledge_base_id: knowledge base to add it to
        :param filename: name the user uploaded it under, shown in source pills
        :param content: the file's bytes
        :raises NotFoundException: if the knowledge base does not exist
        :raises UnsupportedDocumentFormatError: if the format cannot be indexed
        :raises DocumentTooLargeError: if the file exceeds the size cap
        """
        knowledge_base = self.get_knowledge_base_and_check(knowledge_base_id)

        # The bytes are staged in a temp file so that the upload path is the *same* path a source
        # takes: admission check, then snapshot, then row. A rejected upload therefore leaves
        # nothing in the knowledge base's files directory.
        temp_dir = Settings.make_temp_dir()
        temp_path = os.path.join(temp_dir, KnowledgeBaseStorage.sanitise_filename(filename))
        with open(temp_path, "wb") as staged_file:
            staged_file.write(content)

        try:
            return self._add_document_from_file(
                knowledge_base=knowledge_base,
                fetched_path=temp_path,
                filename=filename,
                source_type=UPLOAD_SOURCE_TYPE,
                source_id=None,
                source_metadata=None,
                version_marker=compute_bytes_content_hash(content),
            )
        finally:
            FileHelper.delete_dir(temp_dir)

    def add_document(
        self,
        knowledge_base_id: str,
        source_type: str,
        source_id: str,
        source_metadata: dict | None = None,
    ) -> KnowledgeBaseDocument:
        """Add a document from a registered source: fetch it, snapshot it, record it as ``pending``.

        This is the only place the source system is contacted on the add path, and the last time it
        is contacted for this document until an explicit refresh.

        :raises NotFoundException: if the knowledge base does not exist
        :raises UnknownDocumentSourceError: if no provider is registered for ``source_type``
        :raises UnsupportedDocumentFormatError: if the fetched file's format cannot be indexed
        :raises DocumentTooLargeError: if the fetched file exceeds the size cap
        """
        knowledge_base = self.get_knowledge_base_and_check(knowledge_base_id)
        source = KnowledgeBaseDocumentSourceRegistry.get(source_type)

        fetched = source.fetch_file(source_id, source_metadata)
        try:
            return self._add_document_from_file(
                knowledge_base=knowledge_base,
                fetched_path=fetched.path,
                filename=fetched.filename,
                source_type=source_type,
                source_id=source_id,
                source_metadata=source_metadata,
                version_marker=fetched.version_marker,
            )
        finally:
            # The fetched copy is ours to clean up, per the SourceFetchResult contract.
            FileHelper.delete_file(fetched.path)

    def refresh_document(self, document_id: str) -> DocumentRefresh:
        """Re-fetch a document from its source and replace its snapshot.

        The version marker is recomputed from the fetched bytes, and **only a document whose hash
        moved is queued for re-indexing**: a note someone opened and saved without editing produces
        the same hash, and re-embedding it would cost real money for an identical index. The
        snapshot, the file name and the size are updated either way, so a rename in the source system
        is still followed.

        :return: the document row and whether its content changed
        :raises NotFoundException: if the document does not exist
        :raises UnknownDocumentSourceError: if no provider is registered for its source type
        :raises DocumentSourceOperationNotSupportedError: for a source that cannot be re-fetched,
                an upload being the obvious one
        :raises UnsupportedDocumentFormatError: if the fetched file's format cannot be indexed
        :raises DocumentTooLargeError: if the fetched file exceeds the size cap
        """
        document = self.get_document_and_check(document_id)
        source = KnowledgeBaseDocumentSourceRegistry.get(document.source_type)

        fetched = source.fetch_file(document.source_id, document.source_metadata)
        try:
            previous_snapshot_path = document.snapshot_path
            previous_source_version = document.source_version
            snapshot = self._admit_and_snapshot(
                knowledge_base_id=document.knowledge_base_id,
                document_id=document.id,
                fetched_path=fetched.path,
                filename=fetched.filename,
                version_marker=fetched.version_marker,
            )

            content_changed = snapshot.source_version != previous_source_version
            document = self._save_refreshed_document(
                document, fetched.filename, snapshot, content_changed
            )

            # A renamed source file changes the snapshot path; the old file is then dead weight.
            if previous_snapshot_path != snapshot.snapshot_path:
                FileHelper.delete_file(previous_snapshot_path)

            return DocumentRefresh(document=document, content_changed=content_changed)
        finally:
            FileHelper.delete_file(fetched.path)

    ############################################### DOCUMENTS: BULK IMPORT ###############################################

    def import_documents(
        self,
        knowledge_base_id: str,
        source_type: str,
        criteria: dict,
        engine: KnowledgeBaseEngine,
    ) -> ImportReport:
        """Add, snapshot and index every candidate a source offers for a criterion.

        Provider-agnostic: any source implementing ``list_documents`` gets bulk import for free. The
        whole of the reconciliation logic is the ``source_id`` dedupe below, which is cheap because
        ``source_id`` is on the row.

        **An import only ever adds.** A document whose source no longer matches the criterion is left
        alone — deleting it would make editing a criterion a destructive operation, which is a feature
        with its own confirmation semantics rather than a side effect of importing.

        Every candidate ends up in the report, added or skipped with a reason. That is the point of
        returning a report instead of a count: a tag matching fifty resources of which eight are
        incompatible reads as a clean success otherwise.

        :param knowledge_base_id: knowledge base to import into
        :param source_type: registered source to enumerate
        :param criteria: provider-specific criterion, also stamped into ``source_metadata``
        :param engine: engine of the knowledge base's instance scope, used to index each document
        :raises NotFoundException: if the knowledge base does not exist
        :raises UnknownDocumentSourceError: if no provider is registered for ``source_type``
        :raises DocumentSourceOperationNotSupportedError: if the provider cannot be enumerated
        """
        knowledge_base = self.get_knowledge_base_and_check(knowledge_base_id)
        source = KnowledgeBaseDocumentSourceRegistry.get(source_type)

        candidates = source.list_documents(criteria)
        known_source_ids = {
            document.source_id
            for document in self.get_documents(knowledge_base.id)
            if document.source_id and document.source_type == source_type
        }

        report = ImportReport()
        for candidate in candidates:
            if candidate.source_id in known_source_ids:
                report.skipped.append(
                    self._build_skipped_document(
                        candidate,
                        ImportSkipReason.ALREADY_PRESENT,
                        "Already in this knowledge base. Refresh it to pick up a newer version.",
                    )
                )
                continue

            # Recorded before the add so that a source listing the same id twice cannot add it twice.
            known_source_ids.add(candidate.source_id)

            try:
                document = self.add_document(
                    knowledge_base_id=knowledge_base.id,
                    source_type=source_type,
                    source_id=candidate.source_id,
                    source_metadata=self._build_import_metadata(candidate, criteria),
                )
            except DOCUMENT_REJECTION_ERRORS as err:
                # The reason is written for a user — which format, how big, why the source refused.
                report.skipped.append(
                    self._build_skipped_document(candidate, ImportSkipReason.NOT_INDEXABLE, str(err))
                )
                continue
            except Exception as err:
                # One unreachable resource must not abandon the other forty-nine. Unlike a rejection
                # this is a server-side problem, so it is logged with its stack trace as well.
                Logger.log_exception_stack_trace(err)
                report.skipped.append(
                    self._build_skipped_document(candidate, ImportSkipReason.FAILED, str(err))
                )
                continue

            # Indexing records its own failure on the row instead of raising, so a document that
            # could not be embedded is reported as added-but-not-indexed rather than lost.
            indexed = self.index_document(document.id, engine)
            report.added.append(
                ImportedDocumentDTO(
                    document_id=indexed.id,
                    source_id=candidate.source_id,
                    filename=indexed.filename,
                    index_status=indexed.index_status,
                )
            )

        return report

    ############################################### DOCUMENTS: INDEX ###############################################

    def index_document(
        self, document_id: str, engine: KnowledgeBaseEngine
    ) -> KnowledgeBaseDocument:
        """Index a document's snapshot into the engine, taking a lease for the duration.

        Deliberately **not** one transaction. Two reasons, both about the lease:

        - a lease no other process can read is not a lease, and an uncommitted ``indexing`` row is
          invisible until the run ends — exactly when the lease no longer matters;
        - the engine call embeds and writes, holding an exclusive file lock for as long as that
          takes. A database transaction spanning it would sit open for minutes.

        So each status transition is its own committed transaction, and the engine call sits between
        them. A retry is safe because the engine replaces the document's chunks rather than adding
        to them, so no run can leave duplicates behind.

        What a failed run does **not** do is remove the chunks of the previous successful one: the
        engine deletes them only once loading and embedding have succeeded. So a document can read
        ``error`` while still answering queries with its last good content. That is the better of the
        two failure modes — the alternative is a document that vanishes from retrieval because a
        re-index failed — but it does mean ``index_status`` describes the last *attempt*, not what is
        currently in the index.

        :raises NotFoundException: if the document does not exist
        """
        document = self.get_document_and_check(document_id)
        knowledge_base = document.knowledge_base

        document = self._start_indexing(document)
        try:
            chunk_count = engine.index_document(
                path=document.snapshot_path,
                knowledge_base_id=knowledge_base.id,
                document_id=document.id,
                filename=document.filename,
                chunk_config=knowledge_base.get_chunk_config(),
            )
        except Exception as err:
            Logger.error(f"Failed to index knowledge base document '{document.id}': {err}")
            return self._fail_indexing(document, str(err))

        return self._finish_indexing(document, chunk_count)

    def reclaim_stale_leases(
        self, lease_timeout_seconds: int = DEFAULT_INDEXING_LEASE_TIMEOUT_SECONDS
    ) -> list[KnowledgeBaseDocument]:
        """Turn every dead ``indexing`` row into a retryable ``error``.

        Called when a knowledge base is loaded or synced. Reclaiming is unconditionally safe because
        the engine replaces a document's chunks rather than adding to them, so a retry cannot
        duplicate whatever a half-finished run wrote.

        :return: the documents that were reclaimed
        """
        stale_documents = list(KnowledgeBaseDocument.get_with_stale_lease(lease_timeout_seconds))
        return [
            self._fail_indexing(document, INTERRUPTED_INDEXING_MESSAGE)
            for document in stale_documents
        ]

    ############################################### DOCUMENTS: DELETE ###############################################

    def delete_document(self, document_id: str, engine: KnowledgeBaseEngine) -> None:
        """Delete a document: its chunks, its snapshot and its row, in that order.

        Chunks first for the same reason as
        :meth:`delete_knowledge_base`: a failure must never leave chunks that no row points at.

        :raises NotFoundException: if the document does not exist
        """
        document = self.get_document_and_check(document_id)

        engine.delete_document(document.id)
        snapshot_path = document.snapshot_path

        self._delete_document_row(document)
        FileHelper.delete_file(snapshot_path)

    ############################################### INTERNALS ###############################################

    @staticmethod
    def _check_name_is_free(name: str, allowed_id: str | None = None) -> None:
        """Raise unless this name is available, ignoring the knowledge base already holding it.

        Checked here rather than left to the unique index so callers get a message they can show a
        user instead of a database integrity error.

        :param name: the requested name
        :param allowed_id: knowledge base allowed to keep the name — itself, on an update
        :raises KnowledgeBaseNameAlreadyUsedError: if another knowledge base has this name
        """
        existing = KnowledgeBase.get_by_name(name)
        if existing is not None and existing.id != allowed_id:
            raise KnowledgeBaseNameAlreadyUsedError(
                f"A knowledge base named '{name}' already exists."
            )

    @staticmethod
    def _apply_knowledge_base_dto(
        knowledge_base: KnowledgeBase, knowledge_base_dto: SaveKnowledgeBaseDTO
    ) -> None:
        """Copy the editable fields of a save DTO onto a row, without saving it."""
        knowledge_base.name = knowledge_base_dto.name
        knowledge_base.description = knowledge_base_dto.description
        knowledge_base.instance_scope = knowledge_base_dto.instance_scope
        knowledge_base.chunk_size = knowledge_base_dto.chunk_size
        knowledge_base.chunk_overlap = knowledge_base_dto.chunk_overlap
        knowledge_base.sync_source_type = knowledge_base_dto.sync_source_type
        knowledge_base.sync_config = knowledge_base_dto.sync_config

    @staticmethod
    def _build_import_metadata(candidate: SourceDocumentCandidate, criteria: dict) -> dict:
        """The ``source_metadata`` an imported row carries: the provider's extras plus the criterion.

        ``imported_from`` is what tells an imported document from a hand-picked one. Without it a
        reconciliation pass could not work out which documents are in its scope and which it must
        never touch — one dict key now, no schema change later. The criterion is stored as the
        provider defined it, so this stays true whatever a future provider imports by.

        The service's ``imported_from`` is authoritative: a provider is not expected to set it, but if
        one does, its value is displaced and logged rather than silently lost — a reconciliation pass
        (issue #27) reads this key and must see the criterion the import actually ran on.
        """
        source_metadata = dict(candidate.source_metadata or {})
        if "imported_from" in source_metadata:
            Logger.warning(
                f"Source '{candidate.source_id}' returned its own 'imported_from' metadata; "
                "it is displaced by the import criterion."
            )
        return {**source_metadata, "imported_from": dict(criteria or {})}

    @staticmethod
    def _build_skipped_document(
        candidate: SourceDocumentCandidate, reason: ImportSkipReason, message: str
    ) -> SkippedDocumentDTO:
        """One line of an import report's skip list."""
        return SkippedDocumentDTO(
            source_id=candidate.source_id,
            filename=candidate.filename,
            reason=reason,
            message=message,
        )

    def _add_document_from_file(
        self,
        knowledge_base: KnowledgeBase,
        fetched_path: str,
        filename: str,
        source_type: str,
        source_id: str | None,
        source_metadata: dict | None,
        version_marker: str | None,
    ) -> KnowledgeBaseDocument:
        """Admit a fetched file, snapshot it, and record a ``pending`` row — every source alike.

        Uploads and provider fetches both come through here, which is what stops the two paths from
        drifting into different rules about what may be added.
        """
        # A Model generates its id on construction, so the snapshot path is known before the row is
        # ever saved — which is what lets the snapshot exist first.
        document = KnowledgeBaseDocument()
        snapshot = self._admit_and_snapshot(
            knowledge_base_id=knowledge_base.id,
            document_id=document.id,
            fetched_path=fetched_path,
            filename=filename,
            version_marker=version_marker,
        )
        return self._save_added_document(
            document=document,
            knowledge_base=knowledge_base,
            source_type=source_type,
            source_id=source_id,
            source_metadata=source_metadata,
            filename=filename,
            snapshot=snapshot,
        )

    @staticmethod
    def _admit_and_snapshot(
        knowledge_base_id: str,
        document_id: str,
        fetched_path: str,
        filename: str,
        version_marker: str | None,
    ) -> DocumentSnapshot:
        """Check a fetched file may be indexed, then copy it to its snapshot location.

        Shared by the add and the refresh paths, so an existing document is never held to laxer
        rules than a new one.

        :raises UnsupportedDocumentFormatError: if the format cannot be indexed
        :raises DocumentTooLargeError: if the file exceeds the size cap
        """
        DocumentCompatibility.check_file_is_compatible(fetched_path, filename)

        snapshot_path = KnowledgeBaseStorage.get_snapshot_path(
            knowledge_base_id, document_id, filename
        )
        FileHelper.copy_file(fetched_path, snapshot_path)

        return DocumentSnapshot(
            snapshot_path=snapshot_path,
            size=FileHelper.get_size(snapshot_path),
            # A provider that cannot produce a marker still gets one: the snapshot's own hash.
            source_version=version_marker or compute_file_content_hash(snapshot_path),
        )

    @AiToolkitDbManager.transaction()
    def _save_added_document(
        self,
        document: KnowledgeBaseDocument,
        knowledge_base: KnowledgeBase,
        source_type: str,
        source_id: str | None,
        source_metadata: dict | None,
        filename: str,
        snapshot: DocumentSnapshot,
    ) -> KnowledgeBaseDocument:
        """Record a document whose snapshot is already on disk.

        If this fails the snapshot is deleted rather than left orphaned, but the opposite order —
        row first, snapshot after — is never used: a row without a snapshot would break the
        invariant every other method relies on.
        """
        try:
            document.knowledge_base = knowledge_base
            document.source_type = source_type
            document.source_id = source_id
            document.source_metadata = source_metadata
            document.source_version = snapshot.source_version
            document.snapshot_path = snapshot.snapshot_path
            document.filename = filename
            document.size = snapshot.size
            document.index_status = DocumentIndexStatus.PENDING.value
            document.chunk_count = 0
            document.save()
            return document
        except Exception:
            FileHelper.delete_file(snapshot.snapshot_path)
            raise

    @AiToolkitDbManager.transaction()
    def _save_refreshed_document(
        self,
        document: KnowledgeBaseDocument,
        filename: str,
        snapshot: DocumentSnapshot,
        content_changed: bool,
    ) -> KnowledgeBaseDocument:
        """Point a document at its new snapshot, queueing it for re-indexing only if it changed.

        ``chunk_count`` and ``indexed_at`` are left alone on purpose: the chunks in the index are
        still the previous snapshot's, and they keep answering queries until the re-index runs.
        Zeroing them would report a document as unindexed while it is still retrievable.

        When the content did not change the indexing status is left exactly as it was — a ``done``
        document stays ``done``, and a document that failed to index keeps its error rather than
        quietly reading as pending work that nothing is doing.
        """
        document.source_version = snapshot.source_version
        document.snapshot_path = snapshot.snapshot_path
        document.filename = filename
        document.size = snapshot.size
        if content_changed:
            document.index_status = DocumentIndexStatus.PENDING.value
            document.indexing_started_at = None
            document.error_message = None
        document.save()
        return document

    @AiToolkitDbManager.transaction()
    def _start_indexing(self, document: KnowledgeBaseDocument) -> KnowledgeBaseDocument:
        """Take the lease: the timestamp is stamped in the same write as the status."""
        document.index_status = DocumentIndexStatus.INDEXING.value
        document.indexing_started_at = DateHelper.now_utc()
        document.error_message = None
        document.save()
        return document

    @AiToolkitDbManager.transaction()
    def _finish_indexing(
        self, document: KnowledgeBaseDocument, chunk_count: int
    ) -> KnowledgeBaseDocument:
        """Release the lease and record what was written."""
        document.index_status = DocumentIndexStatus.DONE.value
        document.chunk_count = chunk_count
        document.error_message = None
        document.indexing_started_at = None
        document.indexed_at = DateHelper.now_utc()
        document.save()
        return document

    @AiToolkitDbManager.transaction()
    def _fail_indexing(
        self, document: KnowledgeBaseDocument, error_message: str
    ) -> KnowledgeBaseDocument:
        """Release the lease and keep the reason, which is the only thing a user can act on.

        Used both when the engine raises and when a dead lease is reclaimed — the two differ only in
        the message. ``chunk_count`` is left alone: a failed re-index normally leaves the previous
        chunks in place (the engine replaces them only once loading and embedding have succeeded),
        so zeroing it would under-report a document that is still retrievable.
        """
        document.index_status = DocumentIndexStatus.ERROR.value
        document.error_message = error_message
        document.indexing_started_at = None
        document.save()
        return document

    @AiToolkitDbManager.transaction()
    def _delete_document_row(self, document: KnowledgeBaseDocument) -> None:
        """Delete one document row, its chunks and snapshot having been removed by the caller."""
        document.delete_instance()

    @AiToolkitDbManager.transaction()
    def _delete_knowledge_base_rows(self, knowledge_base: KnowledgeBase) -> None:
        """Delete the documents then the knowledge base, in one transaction.

        The documents are deleted explicitly rather than left to the ``ON DELETE CASCADE``: the
        cascade is a database-level guarantee, and this stays correct whatever the engine enforces.
        """
        KnowledgeBaseDocument.delete().where(
            KnowledgeBaseDocument.knowledge_base == knowledge_base.id
        ).execute()
        knowledge_base.delete_instance()
