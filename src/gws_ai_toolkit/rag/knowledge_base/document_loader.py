"""Turns a file on disk into llama-index documents carrying the chunk metadata.

This is the one place that knows about file formats. V1 indexes **documents only**: PDF, Markdown,
plain text, DOCX, HTML, plus RichText JSON (note content, converted to Markdown by the same rules
``RagResource`` applies). CSV, spreadsheets, data JSON and the legacy ``.doc`` format are rejected,
each with a message naming the reason — see :data:`REJECTED_EXTENSION_REASONS`.

Every reader is unwrapped to plain text and a **single** :class:`Document` is built here, rather than
returning what the reader produced. Readers attach metadata of their own (``PDFReader`` adds a page
label and a file name), and only the four keys below are excluded from the embedded and LLM text — so
a reader's extra key would silently end up inside a vector. Page numbers are not shown anywhere in
V1, so nothing is lost by dropping them; the day a source pill needs one, it belongs in the chunk
metadata schema, not in the text.
"""

import json
import os
from pathlib import Path

from bs4 import BeautifulSoup
from gws_core import RichText, RichTextAggregateDTO
from llama_index.core.schema import Document
from llama_index.readers.file import DocxReader, PDFReader

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
PDF_EXTENSIONS = {".pdf"}
DOCX_EXTENSIONS = {".docx"}
HTML_EXTENSIONS = {".html", ".htm"}
# A .json file is accepted only if it holds rich text; the shape is checked, not assumed.
RICH_TEXT_EXTENSIONS = {".json"}
SUPPORTED_EXTENSIONS = (
    TEXT_EXTENSIONS | PDF_EXTENSIONS | DOCX_EXTENSIONS | HTML_EXTENSIONS | RICH_TEXT_EXTENSIONS
)

# Rejecting tables is a decision, not a gap in the readers — LlamaIndex can load them. At the 15 MB
# cap a CSV is easily 100k rows, so row-level chunks mean 100k embeddings inside one document, and
# those chunks are near-identical in form: they match every query weakly and drag down retrieval for
# the PDFs and notes sharing the index. The failure mode is not "tables answer badly", it is
# "everything answers slightly worse". On top of that, the questions people actually ask a table
# (count, sum, filter, compare) are exactly the ones vector search cannot answer.
TABULAR_REJECTION_REASON = (
    "tabular files are not indexed. One spreadsheet becomes tens of thousands of near-identical "
    "row chunks, which weakens retrieval for every other document in the knowledge base, and the "
    "questions asked of a table (count, sum, filter, compare) are the ones vector search cannot "
    "answer"
)
LEGACY_DOC_REJECTION_REASON = (
    "the legacy Word format cannot be parsed; open it and save it as .docx first"
)
DATA_JSON_REJECTION_REASON = (
    "a .json file is only indexed when it holds rich-text note content, and this one does not; "
    f"if it holds records or measurements, {TABULAR_REJECTION_REASON}"
)

REJECTED_EXTENSION_REASONS = {
    ".csv": TABULAR_REJECTION_REASON,
    ".tsv": TABULAR_REJECTION_REASON,
    ".xlsx": TABULAR_REJECTION_REASON,
    ".xls": TABULAR_REJECTION_REASON,
    ".xlsm": TABULAR_REJECTION_REASON,
    ".doc": LEGACY_DOC_REJECTION_REASON,
}

# Tags that end a line of prose. Everything else is inline, so its text is joined with a space
# rather than split across lines: a sentence broken by a <b> or by the source's own hard wrapping
# should reach the index as one sentence.
HTML_BLOCK_TAGS = [
    "address", "article", "aside", "blockquote", "br", "caption", "dd", "div", "dl", "dt",
    "fieldset", "figcaption", "figure", "footer", "form", "h1", "h2", "h3", "h4", "h5", "h6",
    "header", "hr", "li", "main", "nav", "ol", "p", "pre", "section", "table", "tbody", "td",
    "tfoot", "th", "thead", "title", "tr", "ul",
]
# Not part of any real HTML text; stripped from the source before use so it cannot collide anyway.
HTML_BLOCK_MARKER = "\x00"


class UnsupportedDocumentFormatError(Exception):
    """Raised when a file's format cannot be indexed."""


class EmptyDocumentError(Exception):
    """Raised when a supported format yields no text at all.

    Distinct from an unsupported format, because the fix is different: the format was right and the
    file is the problem — a scanned PDF needing OCR being the usual case.
    """


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
        :raises UnsupportedDocumentFormatError: if the format is not indexable
        :raises EmptyDocumentError: if the file yields no text
        :raises FileNotFoundError: if the file does not exist
        """
        if not os.path.isfile(path):
            raise FileNotFoundError(f"Document file '{path}' does not exist")

        extension = cls.get_extension(filename) or cls.get_extension(path)
        cls.check_extension_is_supported(extension)

        text = cls._extract_text(path, extension)
        if not text.strip():
            # Zero chunks would otherwise be indexed as a success, leaving a document that reports
            # "done" and can never be retrieved. A scanned PDF is the case that gets here.
            raise EmptyDocumentError(
                f"Cannot index '{filename}': no text could be extracted from it. A scanned or "
                f"image-only document has to be converted to text (OCR) before it can be indexed."
            )

        metadata = {
            METADATA_KNOWLEDGE_BASE_ID: knowledge_base_id,
            METADATA_DOCUMENT_ID: document_id,
            METADATA_FILENAME: filename,
            METADATA_ACCESS_SCOPE: access_scope,
        }

        return [
            Document(
                text=text,
                metadata=metadata,
                excluded_embed_metadata_keys=list(CHUNK_METADATA_KEYS),
                excluded_llm_metadata_keys=list(CHUNK_METADATA_KEYS),
            )
        ]

    @classmethod
    def _extract_text(cls, path: str, extension: str) -> str:
        """Extract the indexable text of a file, given the extension that decides the reader.

        The extension is passed in rather than read from ``path`` because a snapshot is stored under
        a sanitised name, and a fetched copy under a temporary one.

        Every branch is explicit and the fallthrough raises: an extension added to
        :data:`SUPPORTED_EXTENSIONS` without a reader would otherwise be read as plain text, which
        for a binary format means indexing its bytes as prose rather than failing.

        :raises UnsupportedDocumentFormatError: if the format has no reader
        """
        if extension in TEXT_EXTENSIONS:
            return cls._read_text_file(path)
        if extension in PDF_EXTENSIONS:
            return cls._read_pdf(path)
        if extension in DOCX_EXTENSIONS:
            return cls._read_docx(path)
        if extension in HTML_EXTENSIONS:
            return cls._read_html(path)
        if extension in RICH_TEXT_EXTENSIONS:
            return cls.read_rich_text(path).to_markdown()

        raise UnsupportedDocumentFormatError(
            f"No reader is wired up for '{extension}' files, although the extension is listed as "
            f"supported. {cls._supported_formats_clause()}"
        )

    @classmethod
    def check_extension_is_supported(cls, extension: str) -> None:
        """Raise if this extension cannot be indexed, naming the reason and what is accepted.

        :raises UnsupportedDocumentFormatError: if the extension is not indexable
        """
        if extension in SUPPORTED_EXTENSIONS:
            return

        described = f"a '{extension}'" if extension else "an extension-less"
        reason = REJECTED_EXTENSION_REASONS.get(extension)
        detail = f"{reason}. " if reason else ""
        raise UnsupportedDocumentFormatError(
            f"Cannot index {described} file: {detail}{cls._supported_formats_clause()}"
        )

    @staticmethod
    def _supported_formats_clause() -> str:
        """The sentence every rejection ends with: naming the reason is only half the message."""
        supported = ", ".join(sorted(SUPPORTED_EXTENSIONS))
        return f"Only {supported} files are supported."

    @classmethod
    def read_rich_text(cls, path: str) -> RichText:
        """Read a ``.json`` file as rich text, refusing anything that is not note content.

        Both shapes ``RagResource`` accepts are accepted here: a bare rich text, and the
        ``RichTextAggregateDTO`` a space note arrives in. Anything else — records, measurements, a
        configuration dump — is data JSON and is rejected rather than indexed as its own source text.

        The two shape checks restate ``RagResource.get_file`` rather than calling it, deliberately:
        the knowledge-base layer must not know about lab resources (only the ``resource`` document
        source imports ``RagResource``), and ``get_file`` returns a temporary ``File`` on disk where
        this needs the text. What is shared is the pair of ``gws_core`` predicates both rely on, so
        the accepted shapes cannot drift apart.

        :raises UnsupportedDocumentFormatError: if the file is not rich-text note content
        """
        name = os.path.basename(path)
        try:
            parsed = json.loads(cls._read_text_file(path))
        except json.JSONDecodeError as exception:
            raise UnsupportedDocumentFormatError(
                f"Cannot index '{name}': it is not valid JSON, so it cannot be rich-text note "
                f"content. {cls._supported_formats_clause()}"
            ) from exception

        if isinstance(parsed, dict):
            if RichText.is_rich_text_json(parsed):
                return RichText.from_json(parsed)
            if RichTextAggregateDTO.json_is_rich_text_aggregate(parsed):
                return RichText(RichTextAggregateDTO.from_json(parsed).richText)

        raise UnsupportedDocumentFormatError(
            f"Cannot index '{name}': {DATA_JSON_REJECTION_REASON}. "
            f"{cls._supported_formats_clause()}"
        )

    @staticmethod
    def get_extension(name: str) -> str:
        """Lower-cased extension of a file name, including the dot ('' if there is none)."""
        return os.path.splitext(name)[1].lower()

    ############################################### READERS ###############################################

    @staticmethod
    def _read_pdf(path: str) -> str:
        """Concatenate the pages of a PDF, dropping the reader's own page metadata."""
        pages = PDFReader().load_data(Path(path))
        return "\n\n".join(page.text for page in pages if page.text)

    @staticmethod
    def _read_docx(path: str) -> str:
        """Read a DOCX through ``docx2txt``, which is what makes the legacy ``.doc`` unreadable."""
        parts = DocxReader().load_data(Path(path))
        return "\n\n".join(part.text for part in parts if part.text)

    @classmethod
    def _read_html(cls, path: str) -> str:
        """Strip an HTML document down to its prose, one line per block.

        Script and style bodies are text to a byte reader and noise to an embedding, so they are
        removed rather than merely unwrapped. Whitespace is then collapsed *within* each block: HTML
        sources wrap their paragraphs, and a newline landing mid-sentence would split a sentence the
        chunker is meant to keep whole.
        """
        # The latin-1 fallback can turn stray bytes into NULs, which would be indistinguishable from
        # the block marker inserted below, so they go before the marker is used.
        content = cls._read_text_file(path).replace(HTML_BLOCK_MARKER, "")

        soup = BeautifulSoup(content, "html.parser")
        for element in soup(["script", "style", "noscript"]):
            element.decompose()

        for element in soup.find_all(HTML_BLOCK_TAGS):
            element.insert_before(HTML_BLOCK_MARKER)
            element.insert_after(HTML_BLOCK_MARKER)

        blocks = (" ".join(block.split()) for block in soup.get_text().split(HTML_BLOCK_MARKER))
        return "\n".join(block for block in blocks if block)

    @staticmethod
    def _read_text_file(path: str) -> str:
        """Read a text file, falling back to latin-1 for files that are not valid UTF-8."""
        try:
            with open(path, encoding="utf-8") as file:
                return file.read()
        except UnicodeDecodeError:
            with open(path, encoding="latin-1") as file:
                return file.read()
