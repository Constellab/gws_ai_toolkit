"""Configuration DTOs for the embedded knowledge-base stack.

Three configurations, deliberately separated because they have different lifetimes:

- :class:`EmbeddingConfig` is an **instance-level** property. Several knowledge bases share one
  LanceDB instance, separated only by a metadata filter, so they must share one vector space.
  Changing the model or the dimensions of an existing instance silently corrupts retrieval, which
  is why the engine validates it against a manifest on open (see ``embedding_manifest.py``).
- :class:`ChunkConfig` is per knowledge base: it only affects documents indexed after the change.
- :class:`RetrievalConfig` is per query (or per chat profile): it affects nothing on disk.
"""

from enum import Enum

from gws_core import BaseModelDTO

# Defaults, as settled in docs/todo/rag_embedded_stack_implementation_plan.md.
DEFAULT_CHUNK_SIZE = 1024
DEFAULT_CHUNK_OVERLAP = 100
DEFAULT_TOP_K = 5
DEFAULT_RRF_K = 60
DEFAULT_OPENAI_EMBEDDING_MODEL = "text-embedding-3-small"
DEFAULT_OPENAI_EMBEDDING_DIMENSIONS = 1536
MOCK_EMBEDDING_MODEL = "hashed-bag-of-words"
MOCK_EMBEDDING_DIMENSIONS = 64


class EmbeddingProvider(str, Enum):
    """Where the embedding vectors come from.

    ``MOCK`` is a deterministic, offline, hashed bag-of-words embedding. It exists so the engine
    tests run without an API key; it must never be used to index a real corpus (its vectors carry
    no semantics, only lexical overlap).
    """

    OPENAI = "openai"
    MOCK = "mock"


class RetrievalMode(str, Enum):
    """Which search a retrieval runs.

    ``HYBRID`` is the V1 default: a vector search and a full-text (BM25) search fused with
    reciprocal rank fusion. ``VECTOR`` and ``FTS`` exist for diagnosis and for tests that need to
    prove the metadata filter holds on every search path, not only on the fused one.

    The score in :class:`~.knowledge_base_models.RetrievedChunk` is **not** comparable across
    modes — see :meth:`~.knowledge_base_engine.KnowledgeBaseEngine.retrieve`.
    """

    VECTOR = "vector"
    FTS = "fts"
    HYBRID = "hybrid"


class EmbeddingConfig(BaseModelDTO):
    """Instance-level embedding configuration.

    ``dimensions`` is part of the identity of the vector space, not a hint: two configurations
    with the same width but a different model (``text-embedding-3-large`` truncated to 1536, or a
    ``mock`` ↔ ``openai`` swap) produce vectors that are numerically compatible and semantically
    unrelated. That is the failure the manifest guards against.
    """

    provider: EmbeddingProvider = EmbeddingProvider.OPENAI
    model: str = DEFAULT_OPENAI_EMBEDDING_MODEL
    # None means "read it from the credentials or the lab settings at creation time".
    api_key: str | None = None
    dimensions: int = DEFAULT_OPENAI_EMBEDDING_DIMENSIONS

    @classmethod
    def mock(cls, dimensions: int = MOCK_EMBEDDING_DIMENSIONS) -> "EmbeddingConfig":
        """Build the deterministic offline configuration used by tests."""
        return cls(
            provider=EmbeddingProvider.MOCK,
            model=MOCK_EMBEDDING_MODEL,
            api_key=None,
            dimensions=dimensions,
        )


class ChunkConfig(BaseModelDTO):
    """Per-knowledge-base chunking configuration.

    Sizes are counted in tokens by the llama-index sentence splitter, not in characters.
    """

    chunk_size: int = DEFAULT_CHUNK_SIZE
    chunk_overlap: int = DEFAULT_CHUNK_OVERLAP


class RetrievalConfig(BaseModelDTO):
    """Per-query retrieval configuration.

    ``score_threshold`` is expressed against the score of the selected ``mode``. In the default
    hybrid mode that is the **fused reciprocal-rank-fusion score**, which is rank-derived and
    typically lands in the 0.01–0.05 range — it is *not* a cosine similarity, so a threshold tuned
    on cosine values (``0.5``, say) rejects everything. Default ``None`` means "no threshold".
    """

    top_k: int = DEFAULT_TOP_K
    score_threshold: float | None = None
    mode: RetrievalMode = RetrievalMode.HYBRID
    # Reciprocal rank fusion constant. LanceDB calls its fusion strategies "rerankers", but RRF is
    # pure arithmetic over ranks: no model, no vendor, no credential.
    rrf_k: int = DEFAULT_RRF_K
