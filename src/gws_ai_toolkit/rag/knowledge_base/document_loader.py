"""Turns a file on disk into llama-index documents carrying the chunk metadata.

This is the one place that knows about file formats. It currently accepts plain text and
Markdown; the remaining accepted formats (PDF, DOCX, HTML, RichText JSON) and the explicit
rejection of tabular files are their own ticket, and land here as extra branches of
:meth:`DocumentLoader.load`.
"""

import os

from llama_index.core.schema import Document

# Metadata written on every document, and therefore on every chunk derived from it. All four keys
# are excluded from the embedded text and from the text handed to an LLM: they are there to filter
# and to attribute a chunk, never to influence its vector or the answer.
METADATA_KNOWLEDGE_BASE_ID = "knowledge_base_id"
METADATA_DOCUMENT_ID = "document_id"
METADATA_FILENAME = "filename"
METADATA_ACCESS_SCOPE = "access_scope"
CHUNK_METADATA_KEYS = [
    METADATA_KNOWLEDGE_BASE_ID,
    METADATA_DOCUMENT_ID,
    METADATA_FILENAME,
    METADATA_ACCESS_SCOPE,
]

# V1 has no per-object permission model, so every chunk is readable by whoever can open the app.
# The field is written now so that real scopes do not require re-embedding the whole store.
DEFAULT_ACCESS_SCOPE = "*"

TEXT_EXTENSIONS = {".txt", ".md"}
SUPPORTED_EXTENSIONS = set(TEXT_EXTENSIONS)


class UnsupportedDocumentFormatError(Exception):
    """Raised when a file's format cannot be indexed."""


class DocumentLoader:
    """Reads a document and attaches the chunk metadata to it."""

    @classmethod
    def load(
        cls,
        path: str,
        knowledge_base_id: str,
        document_id: str,
        filename: str,
        access_scope: str = DEFAULT_ACCESS_SCOPE,
    ) -> list[Document]:
        """Load a file as llama-index documents.

        :param path: path of the file to read (the snapshot, never the source system)
        :param knowledge_base_id: knowledge base the document belongs to
        :param document_id: id carried by every chunk of this document
        :param filename: original file name, shown to users as the source name
        :param access_scope: reserved access marker, ``"*"`` in V1
        :raises UnsupportedDocumentFormatError: if the extension is not indexable
        :raises FileNotFoundError: if the file does not exist
        """
        if not os.path.isfile(path):
            raise FileNotFoundError(f"Document file '{path}' does not exist")

        extension = cls.get_extension(filename) or cls.get_extension(path)
        cls.check_extension_is_supported(extension)

        metadata = {
            METADATA_KNOWLEDGE_BASE_ID: knowledge_base_id,
            METADATA_DOCUMENT_ID: document_id,
            METADATA_FILENAME: filename,
            METADATA_ACCESS_SCOPE: access_scope,
        }

        return [
            Document(
                text=cls._read_text(path),
                metadata=metadata,
                excluded_embed_metadata_keys=list(CHUNK_METADATA_KEYS),
                excluded_llm_metadata_keys=list(CHUNK_METADATA_KEYS),
            )
        ]

    @classmethod
    def check_extension_is_supported(cls, extension: str) -> None:
        """Raise if this extension cannot be indexed, naming what is accepted.

        :raises UnsupportedDocumentFormatError: if the extension is not indexable
        """
        if extension not in SUPPORTED_EXTENSIONS:
            supported = ", ".join(sorted(SUPPORTED_EXTENSIONS))
            raise UnsupportedDocumentFormatError(
                f"Cannot index a '{extension or 'no extension'}' file: "
                f"only {supported} files are supported."
            )

    @staticmethod
    def get_extension(name: str) -> str:
        """Lower-cased extension of a file name, including the dot ('' if there is none)."""
        return os.path.splitext(name)[1].lower()

    @staticmethod
    def _read_text(path: str) -> str:
        """Read a text file, falling back to latin-1 for files that are not valid UTF-8."""
        try:
            with open(path, encoding="utf-8") as file:
                return file.read()
        except UnicodeDecodeError:
            with open(path, encoding="latin-1") as file:
                return file.read()
