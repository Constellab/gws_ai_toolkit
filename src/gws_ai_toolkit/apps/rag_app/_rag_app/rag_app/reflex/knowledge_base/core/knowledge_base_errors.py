"""The document errors that are a user's problem, not a bug.

Adding, refreshing or re-indexing a document can fail for reasons a user can act on: the format is
not indexable, the file is over the cap, the provider is no longer installed, or the source cannot
re-fetch what it once gave. Every one of these carries a message written for a user, so all three
call sites — the detail page, the upload loop and the add-from-source form — turn them into a
``ReflexAppException`` and let the global handler toast them.

The list itself belongs to the knowledge-base layer, next to the provider seam that defines half of
it: the bulk import reports exactly the same failures as reasons for skipping a candidate, and the two
must not drift. It is re-exported here so the app's call sites keep reading as app code.
"""

from gws_ai_toolkit.rag.knowledge_base.sources.knowledge_base_source import (
    DOCUMENT_REJECTION_ERRORS,
)

__all__ = ["DOCUMENT_REJECTION_ERRORS"]
