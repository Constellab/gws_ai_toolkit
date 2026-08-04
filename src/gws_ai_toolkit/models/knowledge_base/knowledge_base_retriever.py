"""Retrieval as the chat loop sees it: a query in, scored chunks out.

The chat conversation must not know that chunks live in LanceDB, that an engine takes a file lock,
or that two knowledge bases of the same profile may sit in different instances. It calls
:meth:`KnowledgeBaseRetriever.retrieve` and gets chunks back.

That indirection is not decoration. It is what lets the conversation be tested with no database and
no embedding provider (a stub retriever), and it is the single place where the
*several knowledge bases → several engines* fan-out lives, so neither the chat loop nor the future
HTTP route re-derives it.

**No engine is ever held.** :class:`EngineKnowledgeBaseRetriever` builds one per call and drops it:
an engine carries a LanceDB connection and takes an ``fcntl`` lock, and the object holding this
retriever is a conversation that gets pickled between Reflex events.
"""

from abc import ABC, abstractmethod

from gws_core import Logger

from gws_ai_toolkit.models.knowledge_base.knowledge_base import KnowledgeBase
from gws_ai_toolkit.models.knowledge_base.knowledge_base_service import KnowledgeBaseService
from gws_ai_toolkit.rag.knowledge_base.knowledge_base_config import DEFAULT_TOP_K, EmbeddingConfig
from gws_ai_toolkit.rag.knowledge_base.knowledge_base_models import RetrievedChunk


class KnowledgeBaseRetriever(ABC):
    """What a knowledge-base chat needs from the retrieval layer, and nothing more."""

    @abstractmethod
    def retrieve(
        self,
        query: str,
        knowledge_base_ids: list[str],
        top_k: int = DEFAULT_TOP_K,
        score_threshold: float | None = None,
    ) -> list[RetrievedChunk]:
        """The chunks most relevant to a query, within the given knowledge bases.

        :param query: the natural-language query
        :param knowledge_base_ids: knowledge bases to search; an empty list must return nothing
                                   rather than everything
        :param top_k: maximum number of chunks to return
        :param score_threshold: drop chunks scoring below this, in the retrieval mode's own scale
        :return: the retrieved chunks, best first
        """


class EngineKnowledgeBaseRetriever(KnowledgeBaseRetriever):
    """Retrieves through the embedded engine, one engine per instance scope, built per call."""

    _embedding_config: EmbeddingConfig

    def __init__(self, embedding_config: EmbeddingConfig) -> None:
        """
        :param embedding_config: the instance-level embedding configuration; only configuration is
                                 held, never an engine (see the module docstring)
        """
        self._embedding_config = embedding_config

    def retrieve(
        self,
        query: str,
        knowledge_base_ids: list[str],
        top_k: int = DEFAULT_TOP_K,
        score_threshold: float | None = None,
    ) -> list[RetrievedChunk]:
        """Search every instance holding one of these knowledge bases, and merge the results.

        A profile may bind knowledge bases living in different instances, and an instance is a
        separate vector space with its own LanceDB directory — so this is one search per scope, each
        already filtered down to the knowledge bases of that scope. The merged list is re-sorted and
        cut back to ``top_k``, so the profile's ``top_k`` stays the number of passages the model
        sees rather than becoming ``top_k`` per instance.

        Merging by score across instances is only as meaningful as the scores are comparable, which
        they are while every instance runs the same retrieval mode — the case today, since mode is
        an engine-level choice. V1 ships a single scope, so this stays a correctness guard rather
        than a hot path.

        :raises EmbeddingManifestMismatchError: if an instance was indexed with another embedding
        """
        ids_by_scope = self._group_ids_by_instance_scope(knowledge_base_ids)
        if not ids_by_scope:
            return []

        chunks: list[RetrievedChunk] = []
        for instance_scope, scope_ids in ids_by_scope.items():
            engine = KnowledgeBaseService.build_engine(
                instance_scope=instance_scope, embedding_config=self._embedding_config
            )
            chunks.extend(
                engine.retrieve(
                    query=query,
                    knowledge_base_ids=scope_ids,
                    top_k=top_k,
                    score_threshold=score_threshold,
                )
            )

        chunks.sort(key=lambda chunk: chunk.score, reverse=True)
        return chunks[:top_k]

    @staticmethod
    def _group_ids_by_instance_scope(knowledge_base_ids: list[str]) -> dict[str, list[str]]:
        """Group the requested knowledge bases by the instance their chunks live in.

        Ids with no knowledge base behind them are dropped and logged rather than raised: a profile
        binding is a soft reference, and a knowledge base deleted after the conversation started
        must not turn the next question into an error.

        :param knowledge_base_ids: the requested ids
        :return: instance scope -> the requested ids held by that instance
        """
        if not knowledge_base_ids:
            return {}

        knowledge_bases = KnowledgeBase.select().where(
            KnowledgeBase.id.in_(list(knowledge_base_ids))
        )
        scope_by_id = {
            knowledge_base.id: knowledge_base.instance_scope for knowledge_base in knowledge_bases
        }

        missing_ids = [
            knowledge_base_id
            for knowledge_base_id in knowledge_base_ids
            if knowledge_base_id not in scope_by_id
        ]
        if missing_ids:
            Logger.warning(
                "Ignoring knowledge base(s) that no longer exist during retrieval: "
                f"{', '.join(missing_ids)}."
            )

        ids_by_scope: dict[str, list[str]] = {}
        for knowledge_base_id in knowledge_base_ids:
            instance_scope = scope_by_id.get(knowledge_base_id)
            if instance_scope is not None:
                ids_by_scope.setdefault(instance_scope, []).append(knowledge_base_id)
        return ids_by_scope
