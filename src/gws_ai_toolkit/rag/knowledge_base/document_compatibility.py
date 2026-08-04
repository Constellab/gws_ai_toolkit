"""The add-time admission check: may this file become a knowledge-base document at all?

It runs on the **fetched file**, so it is source-agnostic: an upload, a lab resource and a provider
registered by another brick all pass through the same rules. Nothing about where the bytes came from
reaches this module — which is the point, since a per-source check would drift the moment a fourth
provider appears.

Rejection happens here rather than at index time because indexing is a background event: a user who
adds a spreadsheet must be told "not this format" while still looking at the add form, not find an
``error`` row later. That is also why the ``.json`` shape is inspected here and not only by the
loader — the extension alone cannot tell a note from a data dump, so an admission check that stopped
at the extension would let a data file through and fail it in the background instead.
"""

import os

from .document_loader import RICH_TEXT_EXTENSIONS, DocumentLoader

# The smaller of the two limits the previous RAG platforms accepted, kept as the V1 cap. It is also
# what bounds the storage duplication the snapshot invariant costs. Owned here rather than imported
# from ``rag/common/rag_enums.py``, which retires with the Dify and RAGFlow services.
MAX_DOCUMENT_SIZE_MB = 15
MAX_DOCUMENT_SIZE_BYTES = MAX_DOCUMENT_SIZE_MB * 1024 * 1024


class DocumentTooLargeError(Exception):
    """Raised when a document exceeds the knowledge-base size cap."""


class DocumentCompatibility:
    """Decides whether a fetched file may be added to a knowledge base."""

    @classmethod
    def check_file_is_compatible(cls, path: str, filename: str) -> None:
        """Raise unless the file at ``path`` can become a knowledge-base document.

        Checks run cheapest first: the extension, then the size, then — for ``.json`` only — the
        content.

        :param path: path of the fetched file
        :param filename: original file name, preferred over ``path`` for deciding the format
                         because a snapshot is stored under a sanitised name and a fetched copy
                         under a temporary one; the path's extension is the fallback when the name
                         carries none
        :raises UnsupportedDocumentFormatError: if the format is not indexable
        :raises DocumentTooLargeError: if the file is above :data:`MAX_DOCUMENT_SIZE_MB`
        :raises FileNotFoundError: if the file does not exist
        """
        extension = DocumentLoader.get_extension(filename) or DocumentLoader.get_extension(path)
        DocumentLoader.check_extension_is_supported(extension)

        if not os.path.isfile(path):
            raise FileNotFoundError(f"Document file '{path}' does not exist")

        cls.check_size_is_within_cap(os.path.getsize(path), filename)

        if extension in RICH_TEXT_EXTENSIONS:
            # Called for the rejection it may raise; the parsed rich text is the loader's business.
            DocumentLoader.read_rich_text(path)

    @classmethod
    def check_size_is_within_cap(cls, size_bytes: int, filename: str) -> None:
        """Raise if a document is above the cap, naming its size and the cap.

        Public because a provider that knows a document's size before producing it can refuse it for
        free: copying a 400 MB resource in order to reject it for size is pointless work, and the
        cap has to be the same number on both paths.

        :raises DocumentTooLargeError: if the size is above :data:`MAX_DOCUMENT_SIZE_MB`
        """
        if size_bytes <= MAX_DOCUMENT_SIZE_BYTES:
            return

        raise DocumentTooLargeError(
            f"Cannot index '{filename}': it is {size_bytes / (1024 * 1024):.1f} MB, above the "
            f"{MAX_DOCUMENT_SIZE_MB} MB limit for an indexed document."
        )
