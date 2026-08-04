"""The built-in ``upload`` document source: bytes a user handed us directly.

An upload is the degenerate case of a source, and worth spelling out: **the uploaded bytes are the
snapshot**. There is no system to re-fetch from, so ``fetch_file`` refuses and ``get_version_marker``
answers "unknown"; the version marker of an uploaded document is the hash of the bytes, computed
once when it is added.

It is registered at import time, and :data:`UPLOAD_SOURCE_TYPE` is what
``KnowledgeBaseService.add_uploaded_document`` stamps on the row, so importing the service is enough
to make the provider available.
"""

from .knowledge_base_source import (
    DocumentSourceOperationNotSupportedError,
    KnowledgeBaseDocumentSource,
    SourceFetchResult,
)

UPLOAD_SOURCE_TYPE = "upload"


class UploadDocumentSource(KnowledgeBaseDocumentSource):
    """Documents uploaded through the app, whose only copy is their snapshot."""

    source_type = UPLOAD_SOURCE_TYPE

    def fetch_file(self, source_id: str | None, source_metadata: dict | None) -> SourceFetchResult:
        """Always refuses: an uploaded document has no source system behind it.

        :raises DocumentSourceOperationNotSupportedError: always
        """
        raise DocumentSourceOperationNotSupportedError(
            "An uploaded document cannot be re-fetched: the uploaded bytes are its snapshot. "
            "Upload the new version instead of refreshing it."
        )

    def get_version_marker(self, source_id: str | None, source_metadata: dict | None) -> str | None:
        """Always ``None``: there is nothing to compare the snapshot against."""
        return None


UploadDocumentSource.register()
