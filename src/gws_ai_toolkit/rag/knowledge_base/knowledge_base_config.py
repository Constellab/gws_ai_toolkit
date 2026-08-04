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
from typing import Any

from gws_core import BaseModelDTO
from pydantic import model_validator

# Defaults, as settled in docs/todo/rag_embedded_stack_implementation_plan.md.
DEFAULT_CHUNK_SIZE = 1024
DEFAULT_CHUNK_OVERLAP = 100
DEFAULT_TOP_K = 5
DEFAULT_RRF_K = 60
DEFAULT_OPENAI_EMBEDDING_MODEL = "text-embedding-3-small"
MOCK_EMBEDDING_MODEL = "hashed-bag-of-words"

# Native vector width of each embedding model — the number of floats one chunk becomes. Keyed by
# model, because the width is a property of the model rather than something a caller should have to
# know: :class:`EmbeddingConfig` resolves it from ``model`` whenever ``dimensions`` is not given.
# It is therefore not exposed as an app parameter; only the manifest tests set it by hand.
#
# The v3 models also accept a *shorter* width than their native one (the vector is truncated,
# trading retrieval accuracy for storage and speed). That is why ``dimensions`` remains settable in
# code — but an instance's width is fixed at first index, so choosing one is a deliberate act.
EMBEDDING_NATIVE_DIMENSIONS: dict[str, int] = {
    "text-embedding-3-small": 1536,
    "text-embedding-3-large": 3072,
    # Legacy, and the one model whose width cannot be shortened at all.
    "text-embedding-ada-002": 1536,
    # Wide enough for the hashed buckets to separate the test corpus, and no wider: a 1536-wide
    # mock would be 24x the arithmetic for no gain.
    MOCK_EMBEDDING_MODEL: 64,
}


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

    It is nevertheless **not something a caller configures**: omit it and it is resolved from
    ``model`` through :data:`EMBEDDING_NATIVE_DIMENSIONS`, which is why no app parameter exposes it.
    Passing one explicitly means asking for a truncated vector, and the manifest then holds whatever
    was asked for.
    """

    provider: EmbeddingProvider = EmbeddingProvider.OPENAI
    model: str = DEFAULT_OPENAI_EMBEDDING_MODEL
    # None means "read it from the credentials or the lab settings at creation time".
    api_key: str | None = None
    # Always a concrete width after validation — see :meth:`_resolve_dimensions`.
    dimensions: int

    @model_validator(mode="before")
    @classmethod
    def _resolve_dimensions(cls, values: Any) -> Any:
        """Fill ``dimensions`` from the model whenever the caller did not choose a width.

        Runs *before* validation so the field itself stays a plain ``int``: the manifest row and the
        arrow schema read a concrete number, and a width resolved once at construction cannot drift
        afterwards the way a lazily-read provider default could.

        :raises ValueError: for a model whose width is unknown and was not given. Guessing here
                would produce the one corruption the manifest cannot catch — a wrong width recorded
                under the right model's name.
        """
        if not isinstance(values, dict) or values.get("dimensions") is not None:
            return values

        model = values.get("model") or DEFAULT_OPENAI_EMBEDDING_MODEL
        dimensions = EMBEDDING_NATIVE_DIMENSIONS.get(model)
        if dimensions is None:
            known = ", ".join(sorted(EMBEDDING_NATIVE_DIMENSIONS))
            raise ValueError(
                f"Unknown embedding model '{model}': its vector width cannot be resolved. Add it to "
                f"EMBEDDING_NATIVE_DIMENSIONS, or pass 'dimensions' explicitly to ask for a "
                f"truncated vector. Known models: {known}."
            )

        return {**values, "dimensions": dimensions}

    @classmethod
    def mock(cls, dimensions: int | None = None) -> "EmbeddingConfig":
        """Build the deterministic offline configuration used by tests.

        :param dimensions: override the mock's own width. Only the manifest tests need this: they
                           prove that a width shared with another model is not mistaken for the
                           same vector space.
        """
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
