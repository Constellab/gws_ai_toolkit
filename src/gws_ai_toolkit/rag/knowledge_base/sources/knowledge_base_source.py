"""Where a document comes from — the provider seam of the knowledge-base stack.

The knowledge-base layer never learns about lab resources, notes, or another brick's storage. It
asks a *source* for a fresh local copy of a document and for a version marker, and that is the
whole contract. Providers register themselves at brick load, the same inversion
``@credentials_type`` uses, so this brick imports none of them.

:meth:`KnowledgeBaseDocumentSource.fetch_file` is called when a document is added and when it is
refreshed or synced — **never when it is indexed**. Indexing reads the snapshot alone, which is what
keeps a deleted resource or an unavailable app from breaking retrieval or re-indexing. A provider
that reaches the source system from ``fetch_file`` is therefore free to be slow, to fail, or to
disappear entirely afterwards.

Version markers are content hashes, so a save that changed nothing does not trigger re-embedding.
:func:`compute_file_content_hash` and :func:`compute_bytes_content_hash` are the one definition of
"the hash", shared by every provider and by the upload path.
"""

import hashlib
from abc import ABC, abstractmethod
from enum import Enum

from gws_core import BaseModelDTO

from gws_ai_toolkit.models.knowledge_base.knowledge_base_dto import KnowledgeBaseDocumentDTO
from gws_ai_toolkit.rag.knowledge_base.document_compatibility import DocumentTooLargeError
from gws_ai_toolkit.rag.knowledge_base.document_loader import UnsupportedDocumentFormatError

_HASH_READ_CHUNK_SIZE = 1024 * 1024


class SourceOpenActionType(str, Enum):
    """How the chat UI opens a source document."""

    DOWNLOAD_SNAPSHOT = "download_snapshot"
    EXTERNAL_LINK = "external_link"


class SourceOpenAction(BaseModelDTO):
    """What the UI should do when a user clicks a source pill.

    Downloading the snapshot always works, because the snapshot is the one copy that is guaranteed
    to exist. A provider overrides this only when it can offer something better — a share link to
    the live resource, say.
    """

    type: SourceOpenActionType = SourceOpenActionType.DOWNLOAD_SNAPSHOT
    url: str | None = None

    @classmethod
    def download_snapshot(cls) -> "SourceOpenAction":
        """Serve the stored snapshot — the fallback that works for every document."""
        return cls(type=SourceOpenActionType.DOWNLOAD_SNAPSHOT)

    @classmethod
    def external_link(cls, url: str) -> "SourceOpenAction":
        """Send the user to the live document in its own system instead."""
        return cls(type=SourceOpenActionType.EXTERNAL_LINK, url=url)


class SourceFetchResult(BaseModelDTO):
    """A fresh local copy of a document, ready to become a snapshot.

    ``path`` is a temporary file **owned by the caller**: the service copies it to the snapshot
    location and then deletes it. A provider must not hand back a path it still needs.
    """

    path: str
    filename: str
    version_marker: str | None = None


class SourceDocumentCandidate(BaseModelDTO):
    """One document a source offers for bulk sync, before anything is fetched."""

    source_id: str
    filename: str
    source_metadata: dict | None = None
    version_marker: str | None = None


class UnknownDocumentSourceError(Exception):
    """Raised when no provider is registered for a source type."""


class DocumentSourceOperationNotSupportedError(Exception):
    """Raised when a provider cannot do what was asked of it (re-fetch, enumerate)."""


# The document failures that are a user's problem rather than a bug: the format is not indexable, the
# file is over the cap, the provider is no longer installed, or the source cannot produce the
# document. Every one carries a message written for a user, so each call site turns it into a reported
# skip instead of a stack trace. Listed here — where two of the four are defined, and which every
# caller already imports — so that a new failure mode is added once rather than in the bulk import,
# the add form, the upload loop and the refresh action.
DOCUMENT_REJECTION_ERRORS = (
    UnsupportedDocumentFormatError,
    DocumentTooLargeError,
    UnknownDocumentSourceError,
    DocumentSourceOperationNotSupportedError,
)


def compute_bytes_content_hash(content: bytes) -> str:
    """Version marker of a document held in memory."""
    return hashlib.sha256(content).hexdigest()


def compute_file_content_hash(path: str) -> str:
    """Version marker of a document on disk, read in chunks so a 15 MB file costs no more."""
    digest = hashlib.sha256()
    with open(path, "rb") as file:
        while chunk := file.read(_HASH_READ_CHUNK_SIZE):
            digest.update(chunk)
    return digest.hexdigest()


class KnowledgeBaseDocumentSource(ABC):
    """A place documents come from: uploads, lab resources, later a document index.

    Subclasses set :attr:`source_type` — the key stored on every document row — and are registered
    once, at brick load, by calling :meth:`register`.
    """

    source_type: str

    @abstractmethod
    def fetch_file(self, source_id: str | None, source_metadata: dict | None) -> SourceFetchResult:
        """Return a fresh local copy of the document, and its version marker.

        Called when a document is added and when it is refreshed or synced, never when it is
        indexed. Format conversions (RichText to Markdown, for instance) happen here, so the
        snapshot is already in a shape the loader accepts.

        :param source_id: opaque id of the document in the source system
        :param source_metadata: provider-specific extras stored on the document row
        :raises DocumentSourceOperationNotSupportedError: if this source cannot produce a copy
        """

    @abstractmethod
    def get_version_marker(self, source_id: str | None, source_metadata: dict | None) -> str | None:
        """Content hash of the document as it stands in the source system.

        ``None`` means the source is gone or unavailable — which a sync reports, and which never
        stops the existing snapshot from being re-indexed.
        """

    def get_open_action(self, document: KnowledgeBaseDocumentDTO) -> SourceOpenAction | None:
        """How the chat UI opens this document. Defaults to downloading the snapshot."""
        return SourceOpenAction.download_snapshot()

    def list_documents(self, criteria: dict) -> list[SourceDocumentCandidate]:
        """Enumerate the documents a bulk import should consider.

        ``criteria`` is provider-specific and used once, by the import that was asked for — it is not
        a subscription stored anywhere. Its keys are also what the service stamps into
        ``source_metadata["imported_from"]``, so keep them small and descriptive.

        :raises DocumentSourceOperationNotSupportedError: unless the provider supports enumeration
        """
        raise DocumentSourceOperationNotSupportedError(
            f"The '{self.source_type}' document source cannot be enumerated, so documents cannot be "
            "imported from it in bulk."
        )

    @classmethod
    def register(cls) -> None:
        """Register this provider, replacing any provider already holding its source type."""
        KnowledgeBaseDocumentSourceRegistry.register(cls())


class KnowledgeBaseDocumentSourceRegistry:
    """The registered document sources, keyed by source type.

    A registry rather than an enum: other bricks add their own providers at load time, and this
    brick must not know their names. That is why ``KnowledgeBaseDocument.source_type`` is a plain
    ``CharField`` too.
    """

    _sources: dict[str, KnowledgeBaseDocumentSource] = {}

    @classmethod
    def register(cls, source: KnowledgeBaseDocumentSource) -> None:
        """Register a provider instance under its own source type."""
        cls._sources[source.source_type] = source

    @classmethod
    def get(cls, source_type: str) -> KnowledgeBaseDocumentSource:
        """The provider for a source type.

        :raises UnknownDocumentSourceError: if nothing is registered for it — which is what a
                document row referring to a brick that is no longer installed looks like
        """
        source = cls._sources.get(source_type)
        if source is None:
            registered = ", ".join(sorted(cls._sources)) or "none"
            raise UnknownDocumentSourceError(
                f"No document source is registered for '{source_type}'. Registered sources: "
                f"{registered}. A brick registers its source at load time."
            )
        return source

    @classmethod
    def get_or_none(cls, source_type: str) -> KnowledgeBaseDocumentSource | None:
        """The provider for a source type, or None — for read paths that must not fail."""
        return cls._sources.get(source_type)

    @classmethod
    def all(cls) -> list[KnowledgeBaseDocumentSource]:
        """Every registered provider."""
        return list(cls._sources.values())

    @classmethod
    def unregister(cls, source_type: str) -> None:
        """Drop a provider. Exists for tests that register a fake source."""
        cls._sources.pop(source_type, None)
