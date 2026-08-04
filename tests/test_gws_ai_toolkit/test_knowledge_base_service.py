import os
import shutil
import tempfile
from unittest.mock import patch

from gws_ai_toolkit.models.knowledge_base.embedding_manifest_model import (
    DbEmbeddingManifestStore,
    EmbeddingManifestModel,
)
from gws_ai_toolkit.models.knowledge_base.knowledge_base import KnowledgeBase
from gws_ai_toolkit.models.knowledge_base.knowledge_base_document import (
    INTERRUPTED_INDEXING_MESSAGE,
    KnowledgeBaseDocument,
)
from gws_ai_toolkit.models.knowledge_base.knowledge_base_dto import (
    DocumentIndexStatus,
    KnowledgeBaseDocumentDTO,
    KnowledgeBaseDTO,
    SaveKnowledgeBaseDTO,
)
from gws_ai_toolkit.models.knowledge_base.knowledge_base_service import (
    KnowledgeBaseNameAlreadyUsedError,
    KnowledgeBaseService,
)
from gws_ai_toolkit.rag.knowledge_base.document_compatibility import (
    MAX_DOCUMENT_SIZE_MB,
    DocumentTooLargeError,
)
from gws_ai_toolkit.rag.knowledge_base.document_loader import UnsupportedDocumentFormatError
from gws_ai_toolkit.rag.knowledge_base.embedding_manifest import (
    EmbeddingManifest,
    EmbeddingManifestMismatchError,
)
from gws_ai_toolkit.rag.knowledge_base.knowledge_base_config import (
    EmbeddingConfig,
    EmbeddingProvider,
)
from gws_ai_toolkit.rag.knowledge_base.knowledge_base_engine import KnowledgeBaseEngine
from gws_ai_toolkit.rag.knowledge_base.knowledge_base_storage import KnowledgeBaseStorage
from gws_ai_toolkit.rag.knowledge_base.sources.knowledge_base_source import (
    DocumentSourceOperationNotSupportedError,
    KnowledgeBaseDocumentSource,
    KnowledgeBaseDocumentSourceRegistry,
    SourceDocumentCandidate,
    SourceFetchResult,
    SourceOpenAction,
    SourceOpenActionType,
    compute_bytes_content_hash,
    compute_file_content_hash,
)
from gws_ai_toolkit.rag.knowledge_base.sources.upload_source import (
    UPLOAD_SOURCE_TYPE,
    UploadDocumentSource,
)
from gws_core import BaseTestCase

TESTDATA_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "testdata", "knowledge_base"
)

FAKE_SOURCE_TYPE = "test_fake_source"

MARKDOWN_CONTENT = (
    "# Sequencing pipeline\n\n"
    "The alignment step aligns reads against the reference genome, then marks duplicates.\n"
)


class FakeDocumentSource(KnowledgeBaseDocumentSource):
    """A document source that exists only in this test file.

    Its whole point is that production never registers it: if ``add_document`` works against it,
    the service really does talk to the registry rather than to a hard-coded list of providers.
    ``available`` turns the source system off, which is how the snapshot invariant is proved.
    """

    source_type = FAKE_SOURCE_TYPE

    def __init__(self, root_dir: str) -> None:
        self.root_dir = root_dir
        self.available = True
        self.fetch_count = 0
        self.share_url = "https://lab.example.org/resource/"
        # When set, the source reports its document under this name instead — a rename in the source
        # system, which a refresh has to follow.
        self.reported_filename: str | None = None

    def _source_path(self, source_id: str) -> str:
        return os.path.join(self.root_dir, source_id)

    def write_source_document(self, source_id: str, content: str) -> str:
        """Put a document in the fake source system, as if someone had created a resource."""
        path = self._source_path(source_id)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as file:
            file.write(content)
        return path

    def delete_source_document(self, source_id: str) -> None:
        os.remove(self._source_path(source_id))

    def fetch_file(self, source_id: str | None, source_metadata: dict | None) -> SourceFetchResult:
        if not self.available:
            raise DocumentSourceOperationNotSupportedError("The fake source system is unavailable.")

        filename = self.reported_filename or os.path.basename(source_id)
        source_path = self._source_path(source_id)
        temp_dir = tempfile.mkdtemp(prefix="fake_source_fetch_")
        temp_path = os.path.join(temp_dir, filename)
        shutil.copyfile(source_path, temp_path)

        self.fetch_count += 1
        return SourceFetchResult(
            path=temp_path,
            filename=filename,
            version_marker=compute_file_content_hash(source_path),
        )

    def get_version_marker(self, source_id: str | None, source_metadata: dict | None) -> str | None:
        if not self.available or not os.path.exists(self._source_path(source_id)):
            return None
        return compute_file_content_hash(self._source_path(source_id))

    def get_open_action(self, document: KnowledgeBaseDocumentDTO) -> SourceOpenAction | None:
        return SourceOpenAction.external_link(f"{self.share_url}{document.source_id}")

    def list_documents(self, sync_config: dict) -> list[SourceDocumentCandidate]:
        return [
            SourceDocumentCandidate(source_id=name, filename=name)
            for name in sorted(os.listdir(self.root_dir))
        ]


# test_knowledge_base_service.py
class TestKnowledgeBaseService(BaseTestCase):
    """Tests for the knowledge-base persistence layer and its service.

    Two things are redirected so the tests stay hermetic: the storage base directory (otherwise
    snapshots would be written into the lab's real brick data directory) and the embedding provider
    (the deterministic ``mock`` embedding, so nothing calls an API).
    """

    service: KnowledgeBaseService
    temp_dir: str
    fake_source: FakeDocumentSource

    def setUp(self) -> None:
        super().setUp()
        # BaseTestCase truncates once per class, so rows from a previous test method would otherwise
        # collide with this one (knowledge-base names are unique).
        KnowledgeBaseDocument.delete().execute()
        KnowledgeBase.delete().execute()
        EmbeddingManifestModel.delete().execute()

        self.temp_dir = tempfile.mkdtemp(prefix="kb_service_test_")
        self._base_dir_patch = patch.object(
            KnowledgeBaseStorage, "get_base_dir", return_value=self.temp_dir
        )
        self._base_dir_patch.start()

        self.service = KnowledgeBaseService()
        self.fake_source = FakeDocumentSource(os.path.join(self.temp_dir, "fake_source"))
        os.makedirs(self.fake_source.root_dir, exist_ok=True)
        KnowledgeBaseDocumentSourceRegistry.register(self.fake_source)

    def tearDown(self) -> None:
        KnowledgeBaseDocumentSourceRegistry.unregister(FAKE_SOURCE_TYPE)
        self._base_dir_patch.stop()
        shutil.rmtree(self.temp_dir, ignore_errors=True)
        super().tearDown()

    ############################################### HELPERS ###############################################

    def _create_knowledge_base(self, name: str = "Protocols") -> KnowledgeBase:
        return self.service.create_knowledge_base(SaveKnowledgeBaseDTO(name=name))

    def _build_engine(self, instance_scope: str = "default") -> KnowledgeBaseEngine:
        return KnowledgeBaseService.build_engine(
            instance_scope=instance_scope, embedding_config=EmbeddingConfig.mock()
        )

    def _upload_markdown(
        self, knowledge_base: KnowledgeBase, filename: str = "pipeline.md"
    ) -> KnowledgeBaseDocument:
        return self.service.add_uploaded_document(
            knowledge_base.id, filename, MARKDOWN_CONTENT.encode("utf-8")
        )

    ############################################### KNOWLEDGE BASE CRUD ###############################################

    def test_create_knowledge_base_applies_the_defaults(self):
        knowledge_base = self._create_knowledge_base()

        self.assertIsNotNone(knowledge_base.id)
        self.assertEqual(knowledge_base.name, "Protocols")
        self.assertEqual(knowledge_base.instance_scope, "default")
        self.assertEqual(knowledge_base.chunk_size, 1024)
        self.assertEqual(knowledge_base.chunk_overlap, 100)
        self.assertIsNone(knowledge_base.sync_source_type)

        chunk_config = knowledge_base.get_chunk_config()
        self.assertEqual(chunk_config.chunk_size, 1024)
        self.assertEqual(chunk_config.chunk_overlap, 100)

    def test_create_knowledge_base_refuses_a_duplicate_name(self):
        self._create_knowledge_base()

        with self.assertRaises(KnowledgeBaseNameAlreadyUsedError):
            self._create_knowledge_base()

    def test_update_knowledge_base_changes_the_chunking_policy(self):
        knowledge_base = self._create_knowledge_base()

        updated = self.service.update_knowledge_base(
            knowledge_base.id,
            SaveKnowledgeBaseDTO(
                name="Protocols v2",
                description="Standard operating procedures",
                chunk_size=256,
                chunk_overlap=16,
                sync_source_type=FAKE_SOURCE_TYPE,
                sync_config={"tag_key": "kb"},
            ),
        )

        self.assertEqual(updated.name, "Protocols v2")
        self.assertEqual(updated.description, "Standard operating procedures")
        self.assertEqual(updated.chunk_size, 256)
        self.assertEqual(updated.sync_source_type, FAKE_SOURCE_TYPE)
        self.assertEqual(updated.sync_config, {"tag_key": "kb"})

    def test_update_knowledge_base_refuses_another_knowledge_bases_name(self):
        first = self._create_knowledge_base("First")
        self._create_knowledge_base("Second")

        with self.assertRaises(KnowledgeBaseNameAlreadyUsedError):
            self.service.update_knowledge_base(first.id, SaveKnowledgeBaseDTO(name="Second"))

        # Keeping its own name is not a conflict with itself.
        renamed = self.service.update_knowledge_base(
            first.id, SaveKnowledgeBaseDTO(name="First", description="unchanged name")
        )
        self.assertEqual(renamed.description, "unchanged name")

    def test_get_all_knowledge_bases_is_ordered_by_name(self):
        self._create_knowledge_base("Zebra")
        self._create_knowledge_base("Alpha")

        names = [knowledge_base.name for knowledge_base in self.service.get_all_knowledge_bases()]

        self.assertEqual(names, ["Alpha", "Zebra"])

    ############################################### ADD AND INDEX ###############################################

    def test_uploaded_document_gets_a_snapshot_and_a_pending_row(self):
        knowledge_base = self._create_knowledge_base()

        document = self._upload_markdown(knowledge_base)

        self.assertEqual(document.index_status, DocumentIndexStatus.PENDING.value)
        self.assertEqual(document.source_type, UPLOAD_SOURCE_TYPE)
        self.assertIsNone(document.source_id)
        self.assertEqual(document.filename, "pipeline.md")
        self.assertEqual(document.size, len(MARKDOWN_CONTENT.encode("utf-8")))
        self.assertEqual(document.chunk_count, 0)
        self.assertIsNone(document.indexed_at)

        # The snapshot exists and holds the uploaded bytes: for an upload it is the only copy.
        self.assertTrue(os.path.isfile(document.snapshot_path))
        with open(document.snapshot_path, encoding="utf-8") as snapshot:
            self.assertEqual(snapshot.read(), MARKDOWN_CONTENT)

        # The version marker is the content hash, so re-uploading the same bytes is detectable.
        self.assertEqual(
            document.source_version, compute_bytes_content_hash(MARKDOWN_CONTENT.encode("utf-8"))
        )

    def test_indexing_an_uploaded_document_takes_it_to_done_with_a_chunk_count(self):
        knowledge_base = self._create_knowledge_base()
        document = self._upload_markdown(knowledge_base)
        engine = self._build_engine()

        indexed = self.service.index_document(document.id, engine)

        self.assertEqual(indexed.index_status, DocumentIndexStatus.DONE.value)
        self.assertGreater(indexed.chunk_count, 0)
        self.assertIsNone(indexed.error_message)
        self.assertIsNone(indexed.indexing_started_at)
        self.assertIsNotNone(indexed.indexed_at)

        # The chunk count is the engine's, and the document row id is the chunks' document_id.
        self.assertEqual(engine.count_chunks(knowledge_base.id), indexed.chunk_count)
        chunks = engine.retrieve("reference genome alignment", [knowledge_base.id])
        self.assertTrue(chunks)
        self.assertEqual(chunks[0].document_id, document.id)
        self.assertEqual(chunks[0].filename, "pipeline.md")

    def test_the_knowledge_bases_chunk_config_is_what_indexing_uses(self):
        knowledge_base = self.service.create_knowledge_base(
            SaveKnowledgeBaseDTO(name="Fine grained", chunk_size=16, chunk_overlap=4)
        )
        document = self.service.add_uploaded_document(
            knowledge_base.id, "long.md", (MARKDOWN_CONTENT * 20).encode("utf-8")
        )

        indexed = self.service.index_document(document.id, self._build_engine())

        # A 1024-token chunk size would produce far fewer chunks: the per-knowledge-base policy is
        # read off the row rather than defaulted by the engine.
        self.assertGreater(indexed.chunk_count, 1)

    def test_indexing_error_path_records_the_message_and_leaves_the_row_in_error(self):
        knowledge_base = self._create_knowledge_base()
        document = self._upload_markdown(knowledge_base)
        engine = self._build_engine()

        # The snapshot disappearing is the honest version of "indexing failed": no mock of the
        # engine, a real failure inside it.
        os.remove(document.snapshot_path)

        failed = self.service.index_document(document.id, engine)

        self.assertEqual(failed.index_status, DocumentIndexStatus.ERROR.value)
        self.assertIn(document.snapshot_path, failed.error_message)
        self.assertIsNone(failed.indexing_started_at)
        self.assertEqual(failed.chunk_count, 0)
        self.assertEqual(engine.count_chunks(), 0)

    def test_a_failed_reindex_keeps_the_previous_chunks_and_their_count(self):
        """`index_status` describes the last attempt, not what is currently in the index.

        The engine replaces a document's chunks only once loading and embedding have succeeded, so a
        failed re-index leaves the last good chunks answering queries. Zeroing `chunk_count` here
        would report a document as unindexed while it is still retrievable — the worse of the two
        inconsistencies, and the reason this is asserted rather than left to chance.
        """
        knowledge_base = self._create_knowledge_base()
        document = self._upload_markdown(knowledge_base)
        engine = self._build_engine()

        indexed = self.service.index_document(document.id, engine)
        good_chunk_count = indexed.chunk_count
        self.assertGreater(good_chunk_count, 0)

        # Break the snapshot, then re-index: the engine fails while loading.
        os.remove(indexed.snapshot_path)
        failed = self.service.index_document(document.id, engine)

        self.assertEqual(failed.index_status, DocumentIndexStatus.ERROR.value)
        self.assertIsNotNone(failed.error_message)
        self.assertEqual(failed.chunk_count, good_chunk_count)
        # And the count is honest: those chunks really are still there and still retrievable.
        self.assertEqual(engine.count_chunks(knowledge_base.id), good_chunk_count)
        self.assertTrue(engine.retrieve("reference genome alignment", [knowledge_base.id]))

    def test_an_unsupported_format_is_refused_at_add_time(self):
        knowledge_base = self._create_knowledge_base()

        with self.assertRaises(UnsupportedDocumentFormatError):
            self.service.add_uploaded_document(knowledge_base.id, "measurements.csv", b"a,b\n1,2\n")

        self.assertEqual(self.service.get_documents(knowledge_base.id), [])

    def test_an_oversized_document_is_refused_at_add_time(self):
        knowledge_base = self._create_knowledge_base()

        with self.assertRaises(DocumentTooLargeError) as context:
            self.service.add_uploaded_document(
                knowledge_base.id, "huge.md", b"x" * (MAX_DOCUMENT_SIZE_MB * 1024 * 1024 + 1)
            )

        self.assertIn("15 MB", str(context.exception))
        self.assertEqual(self.service.get_documents(knowledge_base.id), [])
        # The rejected upload leaves nothing behind on disk either.
        self.assertEqual(os.listdir(KnowledgeBaseStorage.get_files_dir(knowledge_base.id)), [])

    ############################################### LEASE ###############################################

    def test_an_expired_lease_is_reported_as_interrupted_and_can_be_reclaimed(self):
        knowledge_base = self._create_knowledge_base()
        document = self._upload_markdown(knowledge_base)

        # What a killed Reflex background process leaves behind: 'indexing', with a stale lease.
        leased = self.service._start_indexing(document)
        self.assertEqual(leased.index_status, DocumentIndexStatus.INDEXING.value)
        self.assertIsNotNone(leased.indexing_started_at)

        # Fresh lease: still believed to be running, and not reclaimable.
        self.assertFalse(leased.has_stale_lease())
        self.assertEqual(
            leased.to_dto().index_status, DocumentIndexStatus.INDEXING.value
        )
        self.assertEqual(self.service.reclaim_stale_leases(), [])

        # Over-age lease: reported as an error before anything has reclaimed it, so the UI never
        # shows a permanent spinner.
        self.assertTrue(leased.has_stale_lease(lease_timeout_seconds=0))
        stale_dto = leased.to_dto(lease_timeout_seconds=0)
        self.assertEqual(stale_dto.index_status, DocumentIndexStatus.ERROR.value)
        self.assertEqual(stale_dto.error_message, INTERRUPTED_INDEXING_MESSAGE)

        reclaimed = self.service.reclaim_stale_leases(lease_timeout_seconds=0)

        self.assertEqual([document.id for document in reclaimed], [document.id])
        persisted = self.service.get_document_and_check(document.id)
        self.assertEqual(persisted.index_status, DocumentIndexStatus.ERROR.value)
        self.assertEqual(persisted.error_message, INTERRUPTED_INDEXING_MESSAGE)
        self.assertIsNone(persisted.indexing_started_at)

    def test_a_reclaimed_document_can_be_reindexed(self):
        knowledge_base = self._create_knowledge_base()
        document = self._upload_markdown(knowledge_base)
        engine = self._build_engine()

        self.service.index_document(document.id, engine)
        first_count = engine.count_chunks(knowledge_base.id)

        # Interrupt it again, reclaim, retry: re-indexing deletes the document's chunks first, so
        # the retry replaces them instead of duplicating them.
        self.service._start_indexing(self.service.get_document_and_check(document.id))
        self.service.reclaim_stale_leases(lease_timeout_seconds=0)

        reindexed = self.service.index_document(document.id, engine)

        self.assertEqual(reindexed.index_status, DocumentIndexStatus.DONE.value)
        self.assertIsNone(reindexed.error_message)
        self.assertEqual(engine.count_chunks(knowledge_base.id), first_count)

    def test_a_document_indexing_with_no_lease_at_all_counts_as_stale(self):
        """Nothing proves such a row is alive, and leaving it alone is the permanent spinner."""
        knowledge_base = self._create_knowledge_base()
        document = self._upload_markdown(knowledge_base)

        document.index_status = DocumentIndexStatus.INDEXING.value
        document.indexing_started_at = None
        document.save()

        self.assertTrue(document.has_stale_lease())
        self.assertEqual([reclaimed.id for reclaimed in self.service.reclaim_stale_leases()], [document.id])

    ############################################### SNAPSHOT INVARIANT ###############################################

    def test_a_document_added_from_a_source_is_snapshotted_and_indexed_from_the_snapshot(self):
        """The registry seam: a provider production never registers still works end to end."""
        knowledge_base = self._create_knowledge_base()
        self.fake_source.write_source_document("protocol.md", MARKDOWN_CONTENT)

        document = self.service.add_document(knowledge_base.id, FAKE_SOURCE_TYPE, "protocol.md")

        self.assertEqual(document.source_type, FAKE_SOURCE_TYPE)
        self.assertEqual(document.source_id, "protocol.md")
        self.assertEqual(document.index_status, DocumentIndexStatus.PENDING.value)
        self.assertTrue(os.path.isfile(document.snapshot_path))
        self.assertEqual(
            document.source_version, compute_bytes_content_hash(MARKDOWN_CONTENT.encode("utf-8"))
        )
        self.assertEqual(self.fake_source.fetch_count, 1)

        indexed = self.service.index_document(document.id, self._build_engine())

        self.assertEqual(indexed.index_status, DocumentIndexStatus.DONE.value)
        # Indexing never contacts the source: the fetch count is still the one from the add.
        self.assertEqual(self.fake_source.fetch_count, 1)

    def test_indexing_still_succeeds_after_the_source_system_becomes_unavailable(self):
        """The snapshot invariant: this is why indexing reads only ``snapshot_path``."""
        knowledge_base = self._create_knowledge_base()
        self.fake_source.write_source_document("protocol.md", MARKDOWN_CONTENT)
        document = self.service.add_document(knowledge_base.id, FAKE_SOURCE_TYPE, "protocol.md")

        # The resource is deleted and the source system stops answering — the two failure modes the
        # invariant exists for.
        self.fake_source.delete_source_document("protocol.md")
        self.fake_source.available = False

        engine = self._build_engine()
        indexed = self.service.index_document(document.id, engine)

        self.assertEqual(indexed.index_status, DocumentIndexStatus.DONE.value)
        self.assertGreater(indexed.chunk_count, 0)
        self.assertTrue(engine.retrieve("reference genome alignment", [knowledge_base.id]))

        # Re-indexing works too, and the source is now what reports itself as gone.
        reindexed = self.service.index_document(document.id, engine)
        self.assertEqual(reindexed.index_status, DocumentIndexStatus.DONE.value)
        self.assertIsNone(self.fake_source.get_version_marker("protocol.md", None))

    def test_refresh_document_replaces_the_snapshot_and_the_hash(self):
        knowledge_base = self._create_knowledge_base()
        self.fake_source.write_source_document("protocol.md", MARKDOWN_CONTENT)
        document = self.service.add_document(knowledge_base.id, FAKE_SOURCE_TYPE, "protocol.md")
        self.service.index_document(document.id, self._build_engine())
        original_version = document.source_version

        new_content = MARKDOWN_CONTENT + "\nA variant calling step was added.\n"
        self.fake_source.write_source_document("protocol.md", new_content)

        refreshed = self.service.refresh_document(document.id)

        self.assertNotEqual(refreshed.source_version, original_version)
        self.assertEqual(
            refreshed.source_version, compute_bytes_content_hash(new_content.encode("utf-8"))
        )
        self.assertEqual(refreshed.index_status, DocumentIndexStatus.PENDING.value)
        with open(refreshed.snapshot_path, encoding="utf-8") as snapshot:
            self.assertEqual(snapshot.read(), new_content)

    def test_a_refreshed_document_keeps_answering_with_its_old_chunks_until_reindexed(self):
        """A refresh replaces the snapshot only; the index still holds the previous content."""
        knowledge_base = self._create_knowledge_base()
        self.fake_source.write_source_document("protocol.md", MARKDOWN_CONTENT)
        document = self.service.add_document(knowledge_base.id, FAKE_SOURCE_TYPE, "protocol.md")
        engine = self._build_engine()
        indexed = self.service.index_document(document.id, engine)

        self.fake_source.write_source_document("protocol.md", MARKDOWN_CONTENT + "\nNew step.\n")
        refreshed = self.service.refresh_document(document.id)

        self.assertEqual(refreshed.index_status, DocumentIndexStatus.PENDING.value)
        # Not zeroed: the chunks are the previous snapshot's and still serve queries.
        self.assertEqual(refreshed.chunk_count, indexed.chunk_count)
        self.assertIsNotNone(refreshed.indexed_at)
        self.assertTrue(engine.retrieve("reference genome alignment", [knowledge_base.id]))

    def test_refreshing_a_renamed_source_document_leaves_no_orphan_snapshot(self):
        knowledge_base = self._create_knowledge_base()
        self.fake_source.write_source_document("protocol.md", MARKDOWN_CONTENT)
        document = self.service.add_document(knowledge_base.id, FAKE_SOURCE_TYPE, "protocol.md")
        original_snapshot_path = document.snapshot_path

        # The same source id is now reported under a new file name.
        self.fake_source.reported_filename = "protocol_v2.md"

        refreshed = self.service.refresh_document(document.id)

        self.assertEqual(refreshed.filename, "protocol_v2.md")
        self.assertNotEqual(refreshed.snapshot_path, original_snapshot_path)
        self.assertTrue(os.path.isfile(refreshed.snapshot_path))
        self.assertFalse(os.path.exists(original_snapshot_path))

    def test_refreshing_an_uploaded_document_is_refused_with_a_reason(self):
        knowledge_base = self._create_knowledge_base()
        document = self._upload_markdown(knowledge_base)

        with self.assertRaises(DocumentSourceOperationNotSupportedError) as context:
            self.service.refresh_document(document.id)

        self.assertIn("snapshot", str(context.exception))

    ############################################### DELETION ###############################################

    def test_deleting_a_document_removes_its_chunks_its_snapshot_and_its_row(self):
        knowledge_base = self._create_knowledge_base()
        kept = self._upload_markdown(knowledge_base, "kept.md")
        removed = self._upload_markdown(knowledge_base, "removed.md")
        engine = self._build_engine()
        self.service.index_document(kept.id, engine)
        self.service.index_document(removed.id, engine)
        total_chunks = engine.count_chunks(knowledge_base.id)
        snapshot_path = removed.snapshot_path

        self.service.delete_document(removed.id, engine)

        self.assertIsNone(self.service.get_document(removed.id))
        self.assertFalse(os.path.exists(snapshot_path))
        self.assertLess(engine.count_chunks(knowledge_base.id), total_chunks)
        # And the other document is untouched, chunks included.
        self.assertIsNotNone(self.service.get_document(kept.id))
        self.assertTrue(os.path.isfile(kept.snapshot_path))
        self.assertTrue(engine.retrieve("reference genome alignment", [knowledge_base.id]))

    def test_deleting_a_knowledge_base_removes_chunks_snapshots_rows_and_the_files_directory(self):
        knowledge_base = self._create_knowledge_base()
        other = self._create_knowledge_base("Other")
        engine = self._build_engine()

        document = self._upload_markdown(knowledge_base)
        other_document = self._upload_markdown(other)
        self.service.index_document(document.id, engine)
        self.service.index_document(other_document.id, engine)

        files_dir = KnowledgeBaseStorage.get_files_dir(knowledge_base.id)
        self.assertTrue(os.path.isdir(files_dir))

        self.service.delete_knowledge_base(knowledge_base.id, engine)

        self.assertIsNone(self.service.get_knowledge_base(knowledge_base.id))
        self.assertEqual(
            list(KnowledgeBaseDocument.get_by_knowledge_base(knowledge_base.id)), []
        )
        self.assertFalse(os.path.exists(files_dir))
        self.assertEqual(engine.count_chunks(knowledge_base.id), 0)

        # The other knowledge base shares the same engine instance and is untouched.
        self.assertIsNotNone(self.service.get_knowledge_base(other.id))
        self.assertGreater(engine.count_chunks(other.id), 0)
        self.assertTrue(os.path.isfile(other_document.snapshot_path))

    ############################################### DTOS ###############################################

    def test_rows_convert_to_dtos_for_reflex_states(self):
        knowledge_base = self._create_knowledge_base()
        document = self._upload_markdown(knowledge_base)
        self.service.index_document(document.id, self._build_engine())
        document = self.service.get_document_and_check(document.id)

        knowledge_base_dto = knowledge_base.to_dto()
        document_dto = document.to_dto()

        self.assertIsInstance(knowledge_base_dto, KnowledgeBaseDTO)
        self.assertEqual(knowledge_base_dto.id, knowledge_base.id)
        self.assertEqual(knowledge_base_dto.chunk_size, knowledge_base.chunk_size)

        self.assertIsInstance(document_dto, KnowledgeBaseDocumentDTO)
        self.assertEqual(document_dto.knowledge_base_id, knowledge_base.id)
        self.assertEqual(document_dto.index_status, DocumentIndexStatus.DONE.value)
        self.assertEqual(document_dto.chunk_count, document.chunk_count)
        # A server-side path must not travel to a Reflex state.
        self.assertNotIn("snapshot_path", document_dto.to_json_dict())

    def test_get_documents_to_index_lists_only_pending_documents(self):
        knowledge_base = self._create_knowledge_base()
        pending = self._upload_markdown(knowledge_base, "pending.md")
        indexed = self._upload_markdown(knowledge_base, "indexed.md")
        self.service.index_document(indexed.id, self._build_engine())

        to_index = self.service.get_documents_to_index(knowledge_base.id)

        self.assertEqual([document.id for document in to_index], [pending.id])

    ############################################### SOURCE REGISTRY ###############################################

    def test_the_upload_source_is_registered_in_production(self):
        source = KnowledgeBaseDocumentSourceRegistry.get(UPLOAD_SOURCE_TYPE)

        self.assertIsInstance(source, UploadDocumentSource)
        self.assertIsNone(source.get_version_marker(None, None))
        self.assertIn(UPLOAD_SOURCE_TYPE, [s.source_type for s in KnowledgeBaseDocumentSourceRegistry.all()])

    def test_an_unregistered_source_type_names_what_is_registered(self):
        with self.assertRaises(Exception) as context:
            self.service.add_document(
                self._create_knowledge_base().id, "no_such_source", "whatever.md"
            )

        message = str(context.exception)
        self.assertIn("no_such_source", message)
        self.assertIn(UPLOAD_SOURCE_TYPE, message)

    def test_the_open_action_comes_from_the_documents_own_provider(self):
        knowledge_base = self._create_knowledge_base()
        self.fake_source.write_source_document("protocol.md", MARKDOWN_CONTENT)
        from_source = self.service.add_document(knowledge_base.id, FAKE_SOURCE_TYPE, "protocol.md")
        uploaded = self._upload_markdown(knowledge_base)

        source_action = self.service.get_document_open_action(from_source)
        upload_action = self.service.get_document_open_action(uploaded)

        self.assertEqual(source_action.type, SourceOpenActionType.EXTERNAL_LINK)
        self.assertEqual(source_action.url, f"{self.fake_source.share_url}protocol.md")
        self.assertEqual(upload_action.type, SourceOpenActionType.DOWNLOAD_SNAPSHOT)

    def test_the_open_action_falls_back_to_the_snapshot_for_an_unregistered_provider(self):
        """A document whose brick was uninstalled is still readable, because the snapshot is there."""
        knowledge_base = self._create_knowledge_base()
        self.fake_source.write_source_document("protocol.md", MARKDOWN_CONTENT)
        document = self.service.add_document(knowledge_base.id, FAKE_SOURCE_TYPE, "protocol.md")

        KnowledgeBaseDocumentSourceRegistry.unregister(FAKE_SOURCE_TYPE)

        action = self.service.get_document_open_action(document)
        self.assertEqual(action.type, SourceOpenActionType.DOWNLOAD_SNAPSHOT)

    def test_a_source_that_cannot_be_enumerated_says_so(self):
        upload_source = KnowledgeBaseDocumentSourceRegistry.get(UPLOAD_SOURCE_TYPE)

        with self.assertRaises(DocumentSourceOperationNotSupportedError):
            upload_source.list_documents({})

        # The fake source can, which is what a sync will build on.
        self.fake_source.write_source_document("protocol.md", MARKDOWN_CONTENT)
        candidates = self.fake_source.list_documents({})
        self.assertEqual([candidate.source_id for candidate in candidates], ["protocol.md"])

    ############################################### EMBEDDING MANIFEST ###############################################

    def test_the_manifest_is_adopted_into_the_database_and_keyed_by_scope(self):
        knowledge_base = self._create_knowledge_base()
        document = self._upload_markdown(knowledge_base)

        self.service.index_document(document.id, self._build_engine("default"))

        store = DbEmbeddingManifestStore()
        adopted = store.get_manifest("default")
        self.assertEqual(adopted, EmbeddingManifest.from_config(EmbeddingConfig.mock()))

        # Keyed by scope from day one: a second instance is a second row, not a contradiction.
        self.assertIsNone(store.get_manifest("other_lab"))
        self._build_engine("other_lab").count_chunks()
        self.assertIsNotNone(store.get_manifest("other_lab"))
        self.assertEqual(
            EmbeddingManifestModel.select()
            .where(EmbeddingManifestModel.instance_scope == "default")
            .count(),
            1,
        )

    def test_a_manifest_mismatch_in_the_database_refuses_the_instance(self):
        knowledge_base = self._create_knowledge_base()
        document = self._upload_markdown(knowledge_base)
        self.service.index_document(document.id, self._build_engine())

        other_space = KnowledgeBaseService.build_engine(
            instance_scope="default",
            embedding_config=EmbeddingConfig(
                provider=EmbeddingProvider.OPENAI,
                model="text-embedding-3-large",
                api_key="not-used",
                dimensions=EmbeddingConfig.mock().dimensions,
            ),
        )

        with self.assertRaises(EmbeddingManifestMismatchError):
            other_space.retrieve("anything", [knowledge_base.id])

    def test_saving_a_manifest_twice_updates_the_single_row_for_that_scope(self):
        store = DbEmbeddingManifestStore()
        first = EmbeddingManifest(provider="mock", model="hashed-bag-of-words", dimensions=64)
        second = EmbeddingManifest(provider="openai", model="text-embedding-3-small", dimensions=1536)

        store.save_manifest("default", first)
        store.save_manifest("default", second)

        self.assertEqual(store.get_manifest("default"), second)
        self.assertEqual(
            EmbeddingManifestModel.select()
            .where(EmbeddingManifestModel.instance_scope == "default")
            .count(),
            1,
        )
