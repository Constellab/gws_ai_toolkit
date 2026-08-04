import fcntl
import multiprocessing
import os
import shutil
import tempfile
import threading
from unittest import TestCase, skipUnless

from gws_ai_toolkit.rag.knowledge_base.document_loader import (
    METADATA_ACCESS_SCOPE,
    METADATA_DOCUMENT_ID,
    METADATA_FILENAME,
    METADATA_KNOWLEDGE_BASE_ID,
    DocumentLoader,
    UnsupportedDocumentFormatError,
)
from gws_ai_toolkit.rag.knowledge_base.embedding_manifest import (
    EmbeddingManifest,
    EmbeddingManifestMismatchError,
    FileEmbeddingManifestStore,
)
from gws_ai_toolkit.rag.knowledge_base.knowledge_base_config import (
    ChunkConfig,
    EmbeddingConfig,
    EmbeddingProvider,
    RetrievalMode,
)
from gws_ai_toolkit.rag.knowledge_base.knowledge_base_engine import KnowledgeBaseEngine
from gws_ai_toolkit.rag.knowledge_base.knowledge_base_storage import KnowledgeBaseStorage
from llama_index.core.node_parser import SentenceSplitter
from llama_index.core.schema import MetadataMode

TESTDATA_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "testdata", "knowledge_base"
)

# The exact term that exists in ONE document of ONE knowledge base. Every isolation assertion asks
# for it while filtering somewhere else: a corpus where every knowledge base mentions everything
# would pass the same tests while proving nothing.
CANARY_TERM = "ERRCODE-7788"

KB_A = "kb_a"
KB_B = "kb_b"


def index_document_in_this_process(
    instance_dir: str, instance_scope: str, path: str, knowledge_base_id: str, document_id: str
) -> None:
    """Index one document with a fresh engine — the body of the "another process writes" test.

    Defined at module level so it can be the target of a spawned process.
    """
    engine = KnowledgeBaseEngine(
        instance_dir=instance_dir,
        embedding_config=EmbeddingConfig.mock(),
        instance_scope=instance_scope,
    )
    engine.index_document(path, knowledge_base_id, document_id, os.path.basename(path))


# test_knowledge_base_engine.py
class TestKnowledgeBaseEngine(TestCase):
    """Tests for the embedded knowledge-base engine.

    They run entirely offline: the ``mock`` embedding provider is a deterministic hashed
    bag-of-words, so indexing and retrieval exercise the real LanceDB paths with no API key and no
    API call.
    """

    temp_dir: str

    def setUp(self) -> None:
        self.temp_dir = tempfile.mkdtemp(prefix="kb_engine_test_")

    def tearDown(self) -> None:
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    ############################################### HELPERS ###############################################

    def _build_engine(
        self, instance_name: str = "instance", embedding_config: EmbeddingConfig | None = None
    ) -> KnowledgeBaseEngine:
        return KnowledgeBaseEngine(
            instance_dir=os.path.join(self.temp_dir, instance_name),
            embedding_config=embedding_config or EmbeddingConfig.mock(),
            instance_scope=instance_name,
        )

    @staticmethod
    def _testdata_path(filename: str) -> str:
        return os.path.join(TESTDATA_DIR, filename)

    def _index_corpus(self, engine: KnowledgeBaseEngine) -> None:
        """Two knowledge bases, two documents each; the canary lives only in kb_b / doc_b1."""
        engine.index_document(self._testdata_path("pipeline.md"), KB_A, "doc_a1", "pipeline.md")
        engine.index_document(self._testdata_path("samples.txt"), KB_A, "doc_a2", "samples.txt")
        engine.index_document(self._testdata_path("errors.md"), KB_B, "doc_b1", "errors.md")
        engine.index_document(self._testdata_path("deploy.md"), KB_B, "doc_b2", "deploy.md")

    ############################################### INDEXING ###############################################

    def test_indexed_markdown_is_retrievable(self):
        engine = self._build_engine()

        chunk_count = engine.index_document(
            self._testdata_path("pipeline.md"), KB_A, "doc_a1", "pipeline.md"
        )

        self.assertEqual(chunk_count, 1)
        self.assertEqual(engine.count_chunks(), 1)
        self.assertEqual(engine.count_chunks(KB_A), 1)

        chunks = engine.retrieve("reference genome alignment", [KB_A])
        self.assertEqual(len(chunks), 1)
        self.assertIn("aligns reads against the reference genome", chunks[0].content)
        self.assertEqual(chunks[0].knowledge_base_id, KB_A)
        self.assertEqual(chunks[0].document_id, "doc_a1")
        self.assertEqual(chunks[0].filename, "pipeline.md")

    def test_indexed_text_file_is_retrievable(self):
        engine = self._build_engine()

        engine.index_document(self._testdata_path("samples.txt"), KB_A, "doc_a2", "samples.txt")

        chunks = engine.retrieve("laboratory information system", [KB_A])
        self.assertEqual(len(chunks), 1)
        self.assertIn("laboratory information system", chunks[0].content)

    def test_long_document_is_split_into_several_chunks(self):
        engine = self._build_engine()

        chunk_count = engine.index_document(
            self._testdata_path("long_protocol.md"),
            KB_A,
            "doc_long",
            "long_protocol.md",
            chunk_config=ChunkConfig(chunk_size=64, chunk_overlap=8),
        )

        self.assertGreater(chunk_count, 1)
        self.assertEqual(engine.count_chunks(KB_A), chunk_count)

    def test_reindexing_replaces_the_previous_chunks(self):
        """Re-indexing is idempotent, so retrying after an interruption never duplicates chunks."""
        engine = self._build_engine()
        path = self._testdata_path("long_protocol.md")
        chunk_config = ChunkConfig(chunk_size=64, chunk_overlap=8)

        first_count = engine.index_document(
            path, KB_A, "doc_long", "long_protocol.md", chunk_config=chunk_config
        )
        second_count = engine.index_document(
            path, KB_A, "doc_long", "long_protocol.md", chunk_config=chunk_config
        )

        self.assertEqual(first_count, second_count)
        self.assertEqual(engine.count_chunks(), first_count)

    def test_indexed_pdf_is_retrievable(self):
        engine = self._build_engine()

        chunk_count = engine.index_document(
            self._testdata_path("assay_report.pdf"), KB_A, "doc_pdf", "assay_report.pdf"
        )

        self.assertGreater(chunk_count, 0)
        chunks = engine.retrieve("cluster density acceptance threshold", [KB_A])
        self.assertTrue(chunks)
        self.assertEqual(chunks[0].document_id, "doc_pdf")
        self.assertIn("cluster density", " ".join(chunk.content for chunk in chunks))

    def test_indexed_docx_is_retrievable(self):
        engine = self._build_engine()

        engine.index_document(
            self._testdata_path("culture_sop.docx"), KB_A, "doc_docx", "culture_sop.docx"
        )

        chunks = engine.retrieve("thaw the vial water bath", [KB_A])
        self.assertTrue(chunks)
        self.assertIn("thirty-seven degrees Celsius", " ".join(chunk.content for chunk in chunks))

    def test_indexed_html_is_retrievable_without_its_markup(self):
        engine = self._build_engine()

        engine.index_document(
            self._testdata_path("changelog.html"), KB_A, "doc_html", "changelog.html"
        )

        chunks = engine.retrieve("incremental export content hash", [KB_A])
        self.assertTrue(chunks)
        stored_text = " ".join(chunk.content for chunk in chunks)
        self.assertIn("incremental export driven by a content hash", stored_text)
        self.assertNotIn("<p>", stored_text)

    def test_indexed_rich_text_note_is_retrievable_as_markdown(self):
        engine = self._build_engine()

        engine.index_document(
            self._testdata_path("freezer_note.json"), KB_A, "doc_note", "freezer_note.json"
        )

        chunks = engine.retrieve("how do aliquots leave the cryostorage freezer?", [KB_A])
        self.assertTrue(chunks)
        stored_text = " ".join(chunk.content for chunk in chunks)
        self.assertIn("dry ice", stored_text)
        self.assertNotIn("editorVersion", stored_text)

    def test_rejected_extension_names_what_is_supported(self):
        engine = self._build_engine()

        with self.assertRaises(UnsupportedDocumentFormatError) as context:
            engine.index_document(
                self._testdata_path("measurements.csv"), KB_A, "doc_csv", "measurements.csv"
            )

        message = str(context.exception)
        self.assertIn(".csv", message)
        self.assertIn(".md", message)
        self.assertEqual(engine.count_chunks(), 0)

    def test_no_rejected_format_ever_reaches_the_index(self):
        """The loader refuses before any row is written, so a rejection leaves nothing behind."""
        engine = self._build_engine()

        rejected_filenames = (
            "measurements.csv",
            "measurements.xlsx",
            "instrument_readings.json",
            "legacy_report.doc",
        )
        for filename in rejected_filenames:
            with (
                self.subTest(filename=filename),
                self.assertRaises(UnsupportedDocumentFormatError),
            ):
                engine.index_document(
                    self._testdata_path(filename), KB_A, "doc_rejected", filename
                )

        self.assertEqual(engine.count_chunks(), 0)

    def test_chunk_metadata_is_carried_but_kept_out_of_the_text(self):
        """The four metadata keys filter and attribute a chunk; they must not reach a vector or an LLM."""
        documents = DocumentLoader.load(
            path=self._testdata_path("pipeline.md"),
            knowledge_base_id=KB_A,
            document_id="doc_a1",
            filename="pipeline.md",
        )
        nodes = SentenceSplitter(chunk_size=64, chunk_overlap=8).get_nodes_from_documents(documents)
        self.assertTrue(nodes)

        for node in nodes:
            self.assertEqual(node.metadata[METADATA_KNOWLEDGE_BASE_ID], KB_A)
            self.assertEqual(node.metadata[METADATA_DOCUMENT_ID], "doc_a1")
            self.assertEqual(node.metadata[METADATA_FILENAME], "pipeline.md")
            self.assertEqual(node.metadata[METADATA_ACCESS_SCOPE], "*")

            for metadata_mode in (MetadataMode.EMBED, MetadataMode.LLM):
                content = node.get_content(metadata_mode=metadata_mode)
                self.assertNotIn(KB_A, content)
                self.assertNotIn("doc_a1", content)
                self.assertNotIn("pipeline.md", content)

        # And the stored text is the chunk alone: the metadata is not full-text searchable either.
        engine = self._build_engine()
        engine.index_document(self._testdata_path("pipeline.md"), KB_A, "doc_a1", "pipeline.md")
        self.assertEqual(engine.retrieve("doc_a1", [KB_A], mode=RetrievalMode.FTS), [])

    ############################################### ISOLATION ###############################################

    def test_hybrid_retrieval_never_leaks_across_knowledge_bases(self):
        """The knowledge_base_id filter is the only boundary between knowledge bases in one index.

        A LanceDB upgrade could regress filter push-down, and it would fail silently — as chunks of
        another knowledge base appearing in an answer. This assertion is the guard against that.
        """
        engine = self._build_engine()
        self._index_corpus(engine)

        # The canary is reachable when nothing filters it out, so the assertion below is sharp.
        unfiltered = engine.retrieve(CANARY_TERM, [KB_A, KB_B])
        self.assertIn(KB_B, [chunk.knowledge_base_id for chunk in unfiltered])

        scoped_to_a = engine.retrieve(CANARY_TERM, [KB_A])
        self.assertTrue(scoped_to_a)
        self.assertEqual({chunk.knowledge_base_id for chunk in scoped_to_a}, {KB_A})
        self.assertNotIn(CANARY_TERM, " ".join(chunk.content for chunk in scoped_to_a))

    def test_vector_retrieval_never_leaks_across_knowledge_bases(self):
        engine = self._build_engine()
        self._index_corpus(engine)

        scoped_to_a = engine.retrieve(CANARY_TERM, [KB_A], mode=RetrievalMode.VECTOR)

        self.assertTrue(scoped_to_a)
        self.assertEqual({chunk.knowledge_base_id for chunk in scoped_to_a}, {KB_A})

    def test_full_text_retrieval_never_leaks_across_knowledge_bases(self):
        engine = self._build_engine()
        self._index_corpus(engine)

        unfiltered = engine.retrieve(CANARY_TERM, [KB_A, KB_B], mode=RetrievalMode.FTS)
        self.assertEqual({chunk.knowledge_base_id for chunk in unfiltered}, {KB_B})

        scoped_to_a = engine.retrieve(CANARY_TERM, [KB_A], mode=RetrievalMode.FTS)
        self.assertEqual([chunk.knowledge_base_id for chunk in scoped_to_a], [])

    def test_document_ids_narrow_the_search_within_a_knowledge_base(self):
        """AI Expert's relevant-chunks mode: a second filter on the same push-down path."""
        engine = self._build_engine()
        self._index_corpus(engine)

        chunks = engine.retrieve(CANARY_TERM, [KB_B], document_ids=["doc_b2"])

        self.assertTrue(chunks)
        self.assertEqual({chunk.document_id for chunk in chunks}, {"doc_b2"})

        targeted = engine.retrieve(CANARY_TERM, [KB_B], document_ids=["doc_b1"])
        self.assertEqual({chunk.document_id for chunk in targeted}, {"doc_b1"})

    def test_empty_scope_returns_nothing_rather_than_everything(self):
        engine = self._build_engine()
        self._index_corpus(engine)

        self.assertEqual(engine.retrieve(CANARY_TERM, []), [])
        self.assertEqual(engine.retrieve(CANARY_TERM, [KB_B], document_ids=[]), [])
        self.assertEqual(engine.retrieve("   ", [KB_A, KB_B]), [])

    def test_punctuated_questions_reach_the_full_text_side_without_raising(self):
        """Real questions carry apostrophes, colons and quotes, and they go through full-text search."""
        engine = self._build_engine()
        self._index_corpus(engine)

        questions = [
            "What is ERRCODE-7788?",
            "how do I restart the worker's queue (urgent)?",
            'a "quoted" phrase: with AND OR',
        ]
        for question in questions:
            for mode in RetrievalMode:
                self.assertIsInstance(engine.retrieve(question, [KB_A, KB_B], mode=mode), list)

    def test_retrieving_from_an_empty_instance_returns_nothing(self):
        engine = self._build_engine()

        self.assertEqual(engine.retrieve(CANARY_TERM, [KB_A]), [])
        self.assertEqual(engine.count_chunks(), 0)

    ############################################### SCORES ###############################################

    def test_score_threshold_filters_on_the_fused_score(self):
        engine = self._build_engine()
        self._index_corpus(engine)

        chunks = engine.retrieve(CANARY_TERM, [KB_A, KB_B], top_k=6)
        self.assertGreater(len(chunks), 1)
        scores = [chunk.score for chunk in chunks]

        # Reciprocal rank fusion scores sit around 1/(k + rank) with k = 60. The llama-index vector
        # store would instead hand back rank position rescaled to 0..1 — top hit exactly 1.0, last
        # exactly 0.0 — which is the reason the engine reads the LanceDB table directly.
        self.assertLess(max(scores), 0.5)
        self.assertGreater(min(scores), 0.0)

        top_score = max(scores)
        self.assertEqual(engine.retrieve(CANARY_TERM, [KB_A, KB_B], score_threshold=0.0), chunks)
        self.assertEqual(
            engine.retrieve(CANARY_TERM, [KB_A, KB_B], top_k=6, score_threshold=top_score + 0.01),
            [],
        )

        kept = engine.retrieve(CANARY_TERM, [KB_A, KB_B], top_k=6, score_threshold=top_score)
        self.assertTrue(kept)
        self.assertTrue(all(chunk.score >= top_score for chunk in kept))
        self.assertLess(len(kept), len(chunks))

    def test_retrieved_chunk_converts_to_a_chat_source(self):
        engine = self._build_engine()
        self._index_corpus(engine)

        chunk = engine.retrieve(CANARY_TERM, [KB_B])[0]
        source = chunk.to_rag_chat_source()

        self.assertEqual(source.document_id, chunk.document_id)
        self.assertEqual(source.document_name, chunk.filename)
        self.assertEqual(source.score, chunk.score)
        self.assertIsNotNone(source.chunk)
        self.assertEqual(source.chunk.chunk_id, chunk.chunk_id)
        self.assertEqual(source.chunk.content, chunk.content)

    ############################################### DELETION ###############################################

    def test_delete_document_leaves_the_other_documents_alone(self):
        engine = self._build_engine()
        self._index_corpus(engine)
        total = engine.count_chunks()

        engine.delete_document("doc_b1")

        self.assertEqual(engine.count_chunks(), total - 1)
        self.assertEqual(engine.retrieve(CANARY_TERM, [KB_B], mode=RetrievalMode.FTS), [])
        self.assertEqual(engine.count_chunks(KB_A), 2)

    def test_delete_knowledge_base_leaves_the_other_knowledge_bases_alone(self):
        engine = self._build_engine()
        self._index_corpus(engine)

        engine.delete_knowledge_base(KB_B)

        self.assertEqual(engine.count_chunks(KB_B), 0)
        self.assertEqual(engine.count_chunks(KB_A), 2)
        self.assertEqual(engine.retrieve("ingestion worker", [KB_B]), [])

    def test_delete_predicates_survive_single_quotes_in_values(self):
        """Ids and file names reach the predicates from user input; a quote must not break out."""
        engine = self._build_engine()
        engine.index_document(self._testdata_path("pipeline.md"), KB_A, "doc_a1", "pipeline.md")
        engine.index_document(
            self._testdata_path("deploy.md"), "kb_o'brien", "doc_o'brien", "o'brien's deploy.md"
        )
        self.assertEqual(engine.count_chunks(), 2)

        engine.delete_document("doc_o'brien")

        self.assertEqual(engine.count_chunks(), 1)
        self.assertEqual(engine.count_chunks(KB_A), 1)

        engine.index_document(
            self._testdata_path("deploy.md"), "kb_o'brien", "doc_o'brien", "o'brien's deploy.md"
        )
        engine.delete_knowledge_base("kb_o'brien")

        self.assertEqual(engine.count_chunks(), 1)

    ############################################### INSTANCES ###############################################

    def test_two_instances_share_no_rows(self):
        """Scoping is structural: another instance is another directory, not another filter."""
        first = self._build_engine("instance_one")
        second = self._build_engine("instance_two")

        first.index_document(self._testdata_path("errors.md"), KB_B, "doc_b1", "errors.md")
        second.index_document(self._testdata_path("deploy.md"), KB_B, "doc_b2", "deploy.md")

        self.assertNotEqual(first.instance_dir, second.instance_dir)
        self.assertEqual(first.count_chunks(), 1)
        self.assertEqual(second.count_chunks(), 1)

        # Same knowledge base id in both instances, and still no shared row.
        self.assertEqual(
            [chunk.document_id for chunk in first.retrieve(CANARY_TERM, [KB_B])], ["doc_b1"]
        )
        self.assertEqual(
            [chunk.document_id for chunk in second.retrieve(CANARY_TERM, [KB_B])], ["doc_b2"]
        )

    ############################################### CONCURRENCY ###############################################

    def test_a_write_waits_for_the_exclusive_instance_lock(self):
        """Writes take an exclusive flock, so two writers cannot interleave.

        The lock is taken on a lock file rather than on a process-local mutex because several app
        processes writing the same instance is a normal deployment.
        """
        engine = self._build_engine()
        engine.index_document(self._testdata_path("pipeline.md"), KB_A, "doc_a1", "pipeline.md")

        lock_path = KnowledgeBaseStorage.get_lock_file_path(engine.instance_dir)
        lock_fd = os.open(lock_path, os.O_RDWR | os.O_CREAT, 0o644)
        fcntl.flock(lock_fd, fcntl.LOCK_EX)

        indexed_chunks: list[int] = []

        def index_errors_document() -> None:
            indexed_chunks.append(
                engine.index_document(
                    self._testdata_path("errors.md"), KB_B, "doc_b1", "errors.md"
                )
            )

        writer = threading.Thread(target=index_errors_document, daemon=True)
        writer.start()
        try:
            writer.join(timeout=2)
            # Loading and embedding happen before the lock is taken and are near-instant with the
            # mock embedding, so a writer still running after two seconds is waiting on the lock.
            self.assertTrue(writer.is_alive())
            self.assertEqual(indexed_chunks, [])
        finally:
            fcntl.flock(lock_fd, fcntl.LOCK_UN)
            os.close(lock_fd)

        writer.join(timeout=60)
        self.assertFalse(writer.is_alive())
        self.assertEqual(indexed_chunks, [1])
        self.assertEqual(engine.count_chunks(), 2)

    def test_another_process_can_write_to_the_same_instance(self):
        engine = self._build_engine()
        engine.index_document(self._testdata_path("pipeline.md"), KB_A, "doc_a1", "pipeline.md")

        process = multiprocessing.get_context("spawn").Process(
            target=index_document_in_this_process,
            args=(
                engine.instance_dir,
                engine.instance_scope,
                self._testdata_path("errors.md"),
                KB_B,
                "doc_b1",
            ),
        )
        process.start()
        process.join(timeout=300)

        self.assertEqual(process.exitcode, 0)
        self.assertEqual(engine.count_chunks(), 2)
        self.assertEqual(
            [chunk.document_id for chunk in engine.retrieve(CANARY_TERM, [KB_B])], ["doc_b1"]
        )

    ############################################### MANIFEST ###############################################

    def test_missing_manifest_is_adopted_and_written(self):
        engine = self._build_engine()
        manifest_store = FileEmbeddingManifestStore(engine.instance_dir)
        self.assertIsNone(manifest_store.get_manifest(engine.instance_scope))

        engine.index_document(self._testdata_path("pipeline.md"), KB_A, "doc_a1", "pipeline.md")

        manifest = manifest_store.get_manifest(engine.instance_scope)
        self.assertEqual(manifest, EmbeddingManifest.from_config(engine.embedding_config))

    def test_manifest_mismatch_refuses_reads_and_writes(self):
        """Same width, different vector space: no error would ever surface without this guard."""
        engine = self._build_engine()
        self._index_corpus(engine)

        other_space = EmbeddingConfig(
            provider=EmbeddingProvider.OPENAI,
            model="text-embedding-3-large",
            api_key="not-used",
            dimensions=engine.embedding_config.dimensions,
        )
        reopened = self._build_engine("instance", embedding_config=other_space)

        with self.assertRaises(EmbeddingManifestMismatchError) as read_context:
            reopened.retrieve(CANARY_TERM, [KB_B])
        with self.assertRaises(EmbeddingManifestMismatchError):
            reopened.count_chunks()
        with self.assertRaises(EmbeddingManifestMismatchError):
            reopened.index_document(
                self._testdata_path("pipeline.md"), KB_A, "doc_a1", "pipeline.md"
            )
        with self.assertRaises(EmbeddingManifestMismatchError):
            reopened.delete_document("doc_a1")
        with self.assertRaises(EmbeddingManifestMismatchError):
            reopened.delete_knowledge_base(KB_A)

        # The message must name both sides, otherwise it says nothing actionable.
        message = str(read_context.exception)
        self.assertIn(engine.embedding_config.model, message)
        self.assertIn(other_space.model, message)

        # The refusal is a guard, not damage: the instance still reads with its own configuration.
        self.assertGreater(engine.count_chunks(), 0)

    def test_a_matching_manifest_reopens_the_instance(self):
        engine = self._build_engine()
        self._index_corpus(engine)

        reopened = self._build_engine("instance")

        self.assertEqual(reopened.count_chunks(), engine.count_chunks())
        self.assertTrue(reopened.retrieve(CANARY_TERM, [KB_B]))

    ############################################### STORAGE ###############################################

    def test_snapshot_paths_are_sanitised(self):
        path = KnowledgeBaseStorage.get_snapshot_path("kb_a", "doc_1", "../../etc/passwd")

        self.assertTrue(path.endswith("doc_1_passwd"))
        self.assertNotIn("..", path)

    ############################################### REAL EMBEDDING ###############################################

    @skipUnless(os.environ.get("OPENAI_API_KEY"), "requires an OpenAI API key")
    def test_openai_embedding_matches_across_languages(self):
        """A real embedding finds a French document from an English question; the mock cannot."""
        engine = self._build_engine(embedding_config=EmbeddingConfig())
        engine.index_document(
            self._testdata_path("protocole_fr.md"), KB_A, "doc_fr", "protocole_fr.md"
        )

        chunks = engine.retrieve("how are samples frozen before shipping?", [KB_A])

        self.assertTrue(chunks)
        self.assertEqual(chunks[0].document_id, "doc_fr")
