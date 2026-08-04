"""The document errors that are a user's problem, not a bug.

Adding, refreshing or re-indexing a document can fail for reasons a user can act on: the format is
not indexable, the file is over the cap, the provider is no longer installed, or the source cannot
re-fetch what it once gave. Every one of these carries a message written for a user, so all three
call sites — the detail page, the upload loop and the add-from-source form — turn them into a
``ReflexAppException`` and let the global handler toast them.

They are listed here once so a new failure mode is added in one place rather than in three.
"""

from gws_ai_toolkit.rag.knowledge_base.document_compatibility import DocumentTooLargeError
from gws_ai_toolkit.rag.knowledge_base.document_loader import UnsupportedDocumentFormatError
from gws_ai_toolkit.rag.knowledge_base.sources.knowledge_base_source import (
    DocumentSourceOperationNotSupportedError,
    UnknownDocumentSourceError,
)

DOCUMENT_REJECTION_ERRORS = (
    UnsupportedDocumentFormatError,
    DocumentTooLargeError,
    UnknownDocumentSourceError,
    DocumentSourceOperationNotSupportedError,
)
