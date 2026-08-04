"""PROTOTYPE — the portable half of the LanceDB spike.

Pure, no I/O beyond the LanceDB directory it is handed, no printing. The probe runner
(spike.py) imports this; nothing flows the other way.

`MockEmbedding` and the corpus shape are the parts worth lifting into the real code:
the plan's `EmbeddingFactory` needs exactly this deterministic mock so engine tests run
without an API key, and `tests/test_knowledge_base_engine.py` needs a corpus where an
exact term lives in only one knowledge base.
"""

from __future__ import annotations

import hashlib
import math
from dataclasses import dataclass

DIMENSIONS = 64

# The exact term that exists ONLY in knowledge base B. Probe 1 asks for it while filtering
# to A: any hit from B means the filter did not push down.
CANARY_TERM = "ERRCODE-7788"


class MockEmbedding:
    """Deterministic hashed bag-of-words. Same text -> same vector, no network."""

    def __init__(self, dimensions: int = DIMENSIONS) -> None:
        self.dimensions = dimensions

    def embed(self, text: str) -> list[float]:
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


@dataclass
class Chunk:
    """One row. Field names mirror the plan's chunk metadata."""

    chunk_id: str
    content: str
    knowledge_base_id: str
    document_id: str
    filename: str
    access_scope: str = "*"


def build_corpus() -> list[Chunk]:
    """Two knowledge bases. The canary term appears only in B, and only in one of its
    documents, so both the knowledge_base_id and the document_id filter have something
    sharp to prove.
    """
    return [
        Chunk(
            "a1",
            "The sequencing pipeline aligns reads against the reference genome.",
            "kb_a",
            "doc_a1",
            "pipeline.md",
        ),
        Chunk(
            "a2",
            "Quality control drops reads below the configured phred threshold.",
            "kb_a",
            "doc_a1",
            "pipeline.md",
        ),
        Chunk(
            "a3",
            "Sample metadata is imported from the laboratory information system.",
            "kb_a",
            "doc_a2",
            "samples.md",
        ),
        Chunk(
            "b1",
            f"Troubleshooting: {CANARY_TERM} is raised when the ingestion worker "
            f"cannot reach the object store.",
            "kb_b",
            "doc_b1",
            "errors.md",
        ),
        Chunk(
            "b2",
            f"Resolving {CANARY_TERM} requires restarting the ingestion worker and "
            f"replaying the queue.",
            "kb_b",
            "doc_b1",
            "errors.md",
        ),
        Chunk(
            "b3",
            "The deployment guide covers container limits and volume mounts.",
            "kb_b",
            "doc_b2",
            "deploy.md",
        ),
    ]
