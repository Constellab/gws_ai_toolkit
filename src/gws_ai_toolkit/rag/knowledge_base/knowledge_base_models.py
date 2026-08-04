"""DTOs returned by the knowledge-base engine."""

from uuid import uuid4

from gws_core import BaseModelDTO

from ..common.rag_models import RagChatSource, RagChatSourceChunk


class RetrievedChunk(BaseModelDTO):
    """One chunk returned by :meth:`~.knowledge_base_engine.KnowledgeBaseEngine.retrieve`.

    ``score`` carries the score of the retrieval mode that produced it: the fused RRF score in
    hybrid mode, the cosine similarity in vector mode, the BM25 score in full-text mode. Scores
    from different modes are not comparable.
    """

    chunk_id: str
    content: str
    score: float
    knowledge_base_id: str
    document_id: str
    filename: str

    def to_rag_chat_source(self) -> RagChatSource:
        """Convert to the source shape the chat layer already persists and renders."""
        return RagChatSource(
            id=str(uuid4()),
            document_id=self.document_id,
            document_name=self.filename,
            score=self.score,
            chunk=RagChatSourceChunk(
                chunk_id=self.chunk_id,
                content=self.content,
                score=self.score,
            ),
        )
