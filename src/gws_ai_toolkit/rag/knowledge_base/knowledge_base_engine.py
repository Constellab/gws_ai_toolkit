"""The embedded knowledge-base engine: index documents, retrieve chunks.

One engine instance owns one directory. Inside it, a single LanceDB table holds the chunks of
every knowledge base in that instance, told apart by a ``knowledge_base_id`` column — that filter
is the **only** boundary between knowledge bases, which is why the isolation test in
``test_knowledge_base_engine.py`` is a permanent regression guard rather than a one-off check.

Two design decisions are settled and should not be re-litigated (August 2026 spike, recorded in
``docs/todo/rag_embedded_stack_implementation_plan.md``):

- **The engine reads the LanceDB table directly**, not through ``LanceDBVectorStore``. That
  wrapper returns rank position rescaled to 0..1 (top hit always ``1.0``, last always ``0.0``,
  evenly spaced) instead of the fused score, so a threshold against it would mean "in the top
  slice", not "relevant enough", and its meaning would shift with ``top_k``. Owning the table also
  keeps the flat column schema the delete predicates rely on, instead of the wrapper's nested
  ``metadata: struct<...>``.
- **Fusion is LanceDB's ``RRFReranker``** at ``k = 60``. LanceDB calls fusion strategies
  "rerankers"; RRF is pure arithmetic over ranks — no model, no vendor, no credential. "No
  reranker" in the plans means no cross-encoder and no hosted reranking model.

Full-text search needs no maintenance step: rows added after the index was created are searchable
immediately, because LanceDB scans the unindexed fragment.
"""

import fcntl
import os
from collections.abc import Generator, Iterable
from contextlib import contextmanager

import lancedb
import pyarrow as pa
from lancedb.db import DBConnection
from lancedb.index import FTS
from lancedb.query import LanceQueryBuilder
from lancedb.rerankers import RRFReranker
from lancedb.table import Table
from llama_index.core.node_parser import SentenceSplitter
from llama_index.core.schema import MetadataMode

from .document_loader import (
    DEFAULT_ACCESS_SCOPE,
    METADATA_ACCESS_SCOPE,
    METADATA_DOCUMENT_ID,
    METADATA_FILENAME,
    METADATA_KNOWLEDGE_BASE_ID,
    DocumentLoader,
)
from .embedding_factory import EmbeddingFactory, KnowledgeBaseEmbedding
from .embedding_manifest import (
    EmbeddingManifestStore,
    FileEmbeddingManifestStore,
    validate_or_adopt_manifest,
)
from .knowledge_base_config import (
    DEFAULT_TOP_K,
    ChunkConfig,
    EmbeddingConfig,
    RetrievalConfig,
    RetrievalMode,
)
from .knowledge_base_models import RetrievedChunk
from .knowledge_base_storage import DEFAULT_INSTANCE_SCOPE, KnowledgeBaseStorage


class KnowledgeBaseEngine:
    """Indexes documents into a knowledge base and retrieves chunks back out of it.

    Every public method is synchronous. Writes take an exclusive ``fcntl.flock`` on the instance
    directory and reads a shared one, so any process may write: several app instances are a normal
    deployment, the indexing process is killed on idle, and an HTTP route reads from the server
    process. A documented "only this process writes" rule could not enforce any of that.
    """

    CHUNK_TABLE_NAME = "chunks"
    VECTOR_COLUMN = "vector"
    TEXT_COLUMN = "text"
    CHUNK_ID_COLUMN = "chunk_id"

    def __init__(
        self,
        instance_dir: str,
        embedding_config: EmbeddingConfig,
        instance_scope: str = DEFAULT_INSTANCE_SCOPE,
        manifest_store: EmbeddingManifestStore | None = None,
    ) -> None:
        """
        :param instance_dir: directory owned by this instance (one directory = one vector space)
        :param embedding_config: instance-level embedding configuration
        :param instance_scope: name of the instance, the key of its embedding manifest
        :param manifest_store: where the manifest is kept; defaults to a file in ``instance_dir``
        """
        os.makedirs(instance_dir, exist_ok=True)
        self._instance_dir = instance_dir
        self._instance_scope = instance_scope
        self._embedding_config = embedding_config
        self._embedding: KnowledgeBaseEmbedding = EmbeddingFactory.create(embedding_config)
        self._manifest_store = manifest_store or FileEmbeddingManifestStore(instance_dir)
        self._manifest_validated = False

    @classmethod
    def from_scope(
        cls,
        embedding_config: EmbeddingConfig,
        instance_scope: str = DEFAULT_INSTANCE_SCOPE,
        manifest_store: EmbeddingManifestStore | None = None,
    ) -> "KnowledgeBaseEngine":
        """Build the engine for a named instance under the brick's data directory."""
        return cls(
            instance_dir=KnowledgeBaseStorage.get_instance_dir(instance_scope),
            embedding_config=embedding_config,
            instance_scope=instance_scope,
            manifest_store=manifest_store,
        )

    @property
    def instance_dir(self) -> str:
        return self._instance_dir

    @property
    def instance_scope(self) -> str:
        return self._instance_scope

    @property
    def embedding_config(self) -> EmbeddingConfig:
        return self._embedding_config

    ############################################### WRITE ###############################################

    def index_document(
        self,
        path: str,
        knowledge_base_id: str,
        document_id: str,
        filename: str,
        chunk_config: ChunkConfig | None = None,
        access_scope: str = DEFAULT_ACCESS_SCOPE,
    ) -> int:
        """Index a document, replacing any chunks it already had.

        The document's existing chunks are deleted first, so re-indexing is idempotent and safe to
        retry after an interrupted run: a partially indexed document never leaves duplicates
        behind.

        :param path: file to index — the snapshot, never the source system
        :param knowledge_base_id: knowledge base the chunks belong to
        :param document_id: id carried by every chunk of this document
        :param filename: original file name, shown as the source name
        :param chunk_config: chunk size and overlap; defaults to the standard configuration
        :param access_scope: reserved access marker, ``"*"`` in V1
        :return: the number of chunks written
        :raises UnsupportedDocumentFormatError: if the file format cannot be indexed
        :raises EmbeddingManifestMismatchError: if the instance holds another vector space
        """
        chunk_config = chunk_config or ChunkConfig()
        self._validate_manifest()

        documents = DocumentLoader.load(
            path=path,
            knowledge_base_id=knowledge_base_id,
            document_id=document_id,
            filename=filename,
            access_scope=access_scope,
        )
        splitter = SentenceSplitter(
            chunk_size=chunk_config.chunk_size,
            chunk_overlap=chunk_config.chunk_overlap,
        )
        nodes = splitter.get_nodes_from_documents(documents)

        # The metadata keys are excluded from the embedded text, so this is the chunk text alone.
        embedded_texts = [node.get_content(metadata_mode=MetadataMode.EMBED) for node in nodes]
        vectors = self._embedding.embed_texts(embedded_texts)

        rows = [
            {
                self.VECTOR_COLUMN: vector,
                self.CHUNK_ID_COLUMN: f"{document_id}-{index}",
                self.TEXT_COLUMN: node.get_content(metadata_mode=MetadataMode.NONE),
                METADATA_KNOWLEDGE_BASE_ID: knowledge_base_id,
                METADATA_DOCUMENT_ID: document_id,
                METADATA_FILENAME: filename,
                METADATA_ACCESS_SCOPE: access_scope,
            }
            for index, (node, vector) in enumerate(zip(nodes, vectors, strict=True))
        ]

        with self._lock(exclusive=True):
            connection = self._connect()
            table = self._open_table(connection)

            if table is not None:
                self._delete_where(table, self._document_predicate(document_id))

            if not rows:
                return 0

            if table is None:
                table = connection.create_table(
                    self.CHUNK_TABLE_NAME, data=rows, schema=self._build_arrow_schema()
                )
                # Full-text index, needed by hybrid retrieval. Rows added afterwards are searchable
                # without any further maintenance.
                table.create_index(self.TEXT_COLUMN, config=FTS(), replace=True)
            else:
                table.add(rows)

        return len(rows)

    def delete_document(self, document_id: str) -> None:
        """Remove every chunk of one document.

        :raises EmbeddingManifestMismatchError: if the instance holds another vector space
        """
        self._validate_manifest()
        with self._lock(exclusive=True):
            table = self._open_table(self._connect())
            if table is None:
                return
            self._delete_where(table, self._document_predicate(document_id))

    def delete_knowledge_base(self, knowledge_base_id: str) -> None:
        """Remove every chunk of one knowledge base, leaving the other knowledge bases untouched.

        :raises EmbeddingManifestMismatchError: if the instance holds another vector space
        """
        self._validate_manifest()
        with self._lock(exclusive=True):
            table = self._open_table(self._connect())
            if table is None:
                return
            self._delete_where(
                table, self._equals_predicate(METADATA_KNOWLEDGE_BASE_ID, knowledge_base_id)
            )

    ############################################### READ ###############################################

    def retrieve(
        self,
        query: str,
        knowledge_base_ids: list[str],
        top_k: int = DEFAULT_TOP_K,
        score_threshold: float | None = None,
        document_ids: list[str] | None = None,
        mode: RetrievalMode = RetrievalMode.HYBRID,
        rrf_k: int | None = None,
    ) -> list[RetrievedChunk]:
        """Retrieve the chunks most relevant to a query, within the given knowledge bases.

        The ``knowledge_base_ids`` filter is pushed down into the search, in every mode. Passing an
        empty list returns nothing rather than everything: an unscoped search is never what a
        caller means, and treating it as "no filter" would leak across knowledge bases.

        ``score_threshold`` applies to the score of the selected mode: the fused RRF score in
        hybrid mode (rank-derived, roughly 0.01–0.05 — not a cosine similarity), the cosine
        similarity in vector mode, the BM25 score in full-text mode.

        :param query: natural-language or exact-term query
        :param knowledge_base_ids: knowledge bases to search; empty means no result
        :param top_k: maximum number of chunks to return
        :param score_threshold: drop chunks scoring below this, in the mode's own scale
        :param document_ids: narrow the search to these documents (AI Expert's relevant-chunks
                             path); ``None`` means every document of the knowledge bases
        :param mode: which search to run; hybrid by default
        :param rrf_k: reciprocal rank fusion constant, hybrid mode only
        :raises EmbeddingManifestMismatchError: if the instance holds another vector space
        """
        self._validate_manifest()

        if not query or not query.strip():
            return []
        # An empty scope list, or an explicit but empty document list, can only mean "nothing".
        if not knowledge_base_ids or (document_ids is not None and not document_ids):
            return []

        predicate = self._retrieval_predicate(knowledge_base_ids, document_ids)
        retrieval_config = RetrievalConfig(top_k=top_k, score_threshold=score_threshold, mode=mode)
        if rrf_k is not None:
            retrieval_config.rrf_k = rrf_k

        with self._lock(exclusive=False):
            table = self._open_table(self._connect())
            if table is None:
                return []

            builder = self._build_search(table, query, retrieval_config)
            rows = builder.where(predicate, prefilter=True).limit(top_k).to_list()

        chunks = [self._to_retrieved_chunk(row, mode) for row in rows]
        if score_threshold is None:
            return chunks
        return [chunk for chunk in chunks if chunk.score >= score_threshold]

    def count_chunks(self, knowledge_base_id: str | None = None) -> int:
        """Count the chunks of one knowledge base, or of the whole instance.

        :raises EmbeddingManifestMismatchError: if the instance holds another vector space
        """
        self._validate_manifest()
        with self._lock(exclusive=False):
            table = self._open_table(self._connect())
            if table is None:
                return 0
            if knowledge_base_id is None:
                return table.count_rows()
            return table.count_rows(
                filter=self._equals_predicate(METADATA_KNOWLEDGE_BASE_ID, knowledge_base_id)
            )

    ############################################### INTERNALS ###############################################

    def _validate_manifest(self) -> None:
        """Fail closed if this instance was indexed with another embedding.

        Runs outside the instance lock (and so before it is taken) because adopting a missing
        manifest writes a file: taking an exclusive lock while already holding a shared one on the
        same file, in the same process, would deadlock.
        """
        if self._manifest_validated:
            return
        validate_or_adopt_manifest(
            self._manifest_store, self._instance_scope, self._embedding_config
        )
        self._manifest_validated = True

    @contextmanager
    def _lock(self, exclusive: bool) -> Generator[None, None, None]:
        """Guard an instance with a cross-process ``fcntl.flock``: exclusive to write, shared to read."""
        lock_path = KnowledgeBaseStorage.get_lock_file_path(self._instance_dir)
        lock_fd = os.open(lock_path, os.O_RDWR | os.O_CREAT, 0o644)
        try:
            fcntl.flock(lock_fd, fcntl.LOCK_EX if exclusive else fcntl.LOCK_SH)
            try:
                yield
            finally:
                fcntl.flock(lock_fd, fcntl.LOCK_UN)
        finally:
            os.close(lock_fd)

    def _connect(self) -> DBConnection:
        return lancedb.connect(KnowledgeBaseStorage.get_lancedb_dir(self._instance_dir))

    def _open_table(self, connection: DBConnection) -> Table | None:
        """The chunk table, or None when nothing has been indexed in this instance yet."""
        if self.CHUNK_TABLE_NAME not in connection.list_tables().tables:
            return None
        return connection.open_table(self.CHUNK_TABLE_NAME)

    def _build_arrow_schema(self) -> pa.Schema:
        """Flat columns — one row per chunk, metadata as top-level columns.

        Flat is what makes the delete predicates and the pushed-down filters simple; the
        llama-index vector store wrapper would nest them under a ``metadata`` struct instead.
        """
        return pa.schema(
            [
                pa.field(
                    self.VECTOR_COLUMN, pa.list_(pa.float32(), self._embedding.dimensions)
                ),
                pa.field(self.CHUNK_ID_COLUMN, pa.string()),
                pa.field(self.TEXT_COLUMN, pa.string()),
                pa.field(METADATA_KNOWLEDGE_BASE_ID, pa.string()),
                pa.field(METADATA_DOCUMENT_ID, pa.string()),
                pa.field(METADATA_FILENAME, pa.string()),
                pa.field(METADATA_ACCESS_SCOPE, pa.string()),
            ]
        )

    def _build_search(
        self, table: Table, query: str, retrieval_config: RetrievalConfig
    ) -> LanceQueryBuilder:
        """Build the search for the requested mode, before the filter and the limit are applied."""
        if retrieval_config.mode == RetrievalMode.FTS:
            return table.search(query, query_type="fts", fts_columns=self.TEXT_COLUMN)

        query_vector = self._embedding.embed_query(query)

        if retrieval_config.mode == RetrievalMode.VECTOR:
            return table.search(
                query_vector, vector_column_name=self.VECTOR_COLUMN
            ).metric("cosine")

        return (
            table.search(query_type="hybrid", vector_column_name=self.VECTOR_COLUMN)
            .vector(query_vector)
            .text(query)
            .rerank(RRFReranker(K=retrieval_config.rrf_k))
        )

    def _to_retrieved_chunk(self, row: dict, mode: RetrievalMode) -> RetrievedChunk:
        """Map a LanceDB row to a DTO, reading the score column that belongs to the mode."""
        if mode == RetrievalMode.HYBRID:
            # The real fused RRF score, which is the whole reason the table is read directly.
            score = float(row.get("_relevance_score") or 0.0)
        elif mode == RetrievalMode.VECTOR:
            # Cosine distance, turned back into a similarity.
            score = 1.0 - float(row.get("_distance") or 0.0)
        else:
            score = float(row.get("_score") or 0.0)

        return RetrievedChunk(
            chunk_id=row[self.CHUNK_ID_COLUMN],
            content=row[self.TEXT_COLUMN],
            score=score,
            knowledge_base_id=row[METADATA_KNOWLEDGE_BASE_ID],
            document_id=row[METADATA_DOCUMENT_ID],
            filename=row[METADATA_FILENAME],
        )

    def _retrieval_predicate(
        self, knowledge_base_ids: list[str], document_ids: list[str] | None
    ) -> str:
        """The pushed-down filter: the only boundary between knowledge bases in one index."""
        predicate = self._in_predicate(METADATA_KNOWLEDGE_BASE_ID, knowledge_base_ids)
        if document_ids:
            predicate = f"{predicate} AND {self._in_predicate(METADATA_DOCUMENT_ID, document_ids)}"
        return predicate

    def _document_predicate(self, document_id: str) -> str:
        return self._equals_predicate(METADATA_DOCUMENT_ID, document_id)

    @classmethod
    def _delete_where(cls, table: Table, predicate: str) -> None:
        """The single place chunks are deleted, so predicate building stays in one file."""
        table.delete(predicate)

    @classmethod
    def _equals_predicate(cls, column: str, value: str) -> str:
        return f"`{column}` = {cls._quote_value(value)}"

    @classmethod
    def _in_predicate(cls, column: str, values: Iterable[str]) -> str:
        quoted = ", ".join(cls._quote_value(value) for value in values)
        return f"`{column}` IN ({quoted})"

    @staticmethod
    def _quote_value(value: str) -> str:
        """Quote a value for a LanceDB predicate.

        Ids and file names reach the predicates from user input, and a single quote in a value
        would otherwise break out of the literal: a delete that matches nothing is the dangerous
        case, because re-indexing would then duplicate chunks instead of replacing them. LanceDB
        expects a single quote to be doubled.
        """
        escaped = str(value).replace("'", "''")
        return f"'{escaped}'"
