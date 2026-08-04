"""The one document an AI Expert conversation is about, as the chat loop needs it.

A :class:`~gws_ai_toolkit.models.knowledge_base.knowledge_base_document.KnowledgeBaseDocument` is a
Peewee row; this is the handful of facts a conversation actually uses, as a value:

- ``document_id`` — the row id, which **is** the ``document_id`` carried by every chunk of this
  document in the vector store. That identity is what lets ``relevant_chunks`` narrow a retrieval to
  this document with no translation step.
- ``knowledge_base_id`` — the scope that retrieval is filtered to. A document id alone is not enough:
  the engine refuses an unscoped search.
- ``snapshot_path`` — what ``full_text_chunk`` reads. The snapshot always exists (snapshot-on-add), so
  a source system that went away does not stop a conversation.

Holding a value rather than a row matters twice over: the conversation is pickled between Reflex
events, and a test can build one from a file on disk with no database at all.

**This is a backend value, never a frontend one.** ``snapshot_path`` is a server path, which is why
``KnowledgeBaseDocumentDTO`` deliberately omits it — anything putting this on a Reflex state must keep
it in a backend var.
"""

from gws_core import BaseModelDTO

from gws_ai_toolkit.models.knowledge_base.knowledge_base_document import KnowledgeBaseDocument
from gws_ai_toolkit.rag.knowledge_base.document_loader import DocumentLoader


class AiExpertDocument(BaseModelDTO):
    """The document an AI Expert conversation answers about.

    Attributes:
        document_id: Id of the knowledge-base document, and of its chunks in the vector store.
        knowledge_base_id: Knowledge base holding it, which scopes every retrieval.
        filename: Name the document was added under, shown to the user and given to the model.
        snapshot_path: Server path of the stored snapshot, read by ``full_text_chunk``.
    """

    document_id: str
    knowledge_base_id: str
    filename: str
    snapshot_path: str

    @classmethod
    def from_document(cls, document: KnowledgeBaseDocument) -> "AiExpertDocument":
        """Read the facts a conversation needs off a knowledge-base document row.

        Args:
            document: The row the conversation is about.

        Returns:
            The value the conversation and its agent carry.
        """
        return cls(
            document_id=document.id,
            # Read straight off the foreign-key column, so no extra query resolves the relation.
            knowledge_base_id=document.knowledge_base_id,
            filename=document.filename,
            snapshot_path=document.snapshot_path,
        )

    def read_text(self) -> str:
        """The document's full text, extracted from its snapshot exactly as indexing extracts it.

        Read on every turn rather than cached: the text of a 15 MB document has no business sitting
        on a pickled Reflex state for the life of a conversation, and re-reading a local file is
        cheap by comparison. A refreshed snapshot is therefore also picked up by the next question.

        Returns:
            The text handed to the model in ``full_text_chunk`` mode.

        Raises:
            FileNotFoundError: If the snapshot is gone.
            UnsupportedDocumentFormatError: If its format has no reader.
            EmptyDocumentError: If no text can be extracted from it.
        """
        return DocumentLoader.load_text(self.snapshot_path, self.filename)
