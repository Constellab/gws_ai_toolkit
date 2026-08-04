"""Embedding providers for the knowledge-base engine.

This is the single swap point for the vector space: the engine only ever sees
:class:`KnowledgeBaseEmbedding`, so replacing OpenAI with a local model later touches this file
and the manifest, and nothing else.
"""

import hashlib
import math
from abc import ABC, abstractmethod

from llama_index.embeddings.openai import OpenAIEmbedding

from .knowledge_base_config import EmbeddingConfig, EmbeddingProvider


class KnowledgeBaseEmbedding(ABC):
    """Minimal embedding surface the engine depends on."""

    dimensions: int

    def __init__(self, dimensions: int) -> None:
        self.dimensions = dimensions

    @abstractmethod
    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        """Embed chunk texts, in order."""

    @abstractmethod
    def embed_query(self, query: str) -> list[float]:
        """Embed a search query."""


class MockEmbedding(KnowledgeBaseEmbedding):
    """Deterministic hashed bag-of-words embedding — same text gives the same vector, no network.

    Lifted from the August 2026 LanceDB spike (``spike/lancedb-hybrid``). It exists so the engine
    tests exercise the real indexing and retrieval paths with no API key and no API call. Lexical
    overlap is all it captures, which is enough to rank a canary term first and nothing more: it
    must never index a real corpus.
    """

    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        return [self._embed(text) for text in texts]

    def embed_query(self, query: str) -> list[float]:
        return self._embed(query)

    def _embed(self, text: str) -> list[float]:
        vector = [0.0] * self.dimensions
        for token in self._tokenize(text):
            digest = hashlib.sha1(token.encode("utf-8")).digest()
            bucket = int.from_bytes(digest[:4], "big") % self.dimensions
            sign = 1.0 if digest[4] % 2 == 0 else -1.0
            vector[bucket] += sign

        norm = math.sqrt(sum(value * value for value in vector))
        if norm == 0.0:
            # An all-zero vector makes cosine distance undefined; bias one dimension.
            vector[0] = 1.0
            return vector
        return [value / norm for value in vector]

    @staticmethod
    def _tokenize(text: str) -> list[str]:
        return [token for token in text.lower().replace("\n", " ").split(" ") if token]


class OpenAIKnowledgeBaseEmbedding(KnowledgeBaseEmbedding):
    """OpenAI embeddings, through the llama-index client."""

    def __init__(self, model: str, dimensions: int, api_key: str | None) -> None:
        super().__init__(dimensions)
        self._embedding = OpenAIEmbedding(model=model, dimensions=dimensions, api_key=api_key)

    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        return self._embedding.get_text_embedding_batch(texts)

    def embed_query(self, query: str) -> list[float]:
        return self._embedding.get_query_embedding(query)


class EmbeddingFactory:
    """Builds the embedding described by an :class:`EmbeddingConfig`."""

    @classmethod
    def create(cls, config: EmbeddingConfig) -> KnowledgeBaseEmbedding:
        """Instantiate the configured embedding provider.

        :param config: instance-level embedding configuration
        :raises ValueError: if the provider is unknown
        """
        if config.provider == EmbeddingProvider.MOCK:
            return MockEmbedding(config.dimensions)

        if config.provider == EmbeddingProvider.OPENAI:
            return OpenAIKnowledgeBaseEmbedding(
                model=config.model,
                dimensions=config.dimensions,
                api_key=config.api_key,
            )

        raise ValueError(f"Unknown embedding provider '{config.provider}'")
