import json
import os
import shutil
import tempfile
from unittest import TestCase

from gws_ai_toolkit.rag.knowledge_base.document_compatibility import (
    MAX_DOCUMENT_SIZE_MB,
    DocumentCompatibility,
    DocumentTooLargeError,
)
from gws_ai_toolkit.rag.knowledge_base.document_loader import (
    METADATA_ACCESS_SCOPE,
    METADATA_DOCUMENT_ID,
    METADATA_FILENAME,
    METADATA_KNOWLEDGE_BASE_ID,
    DocumentLoader,
    EmptyDocumentError,
    UnsupportedDocumentFormatError,
)
from llama_index.core.schema import MetadataMode

TESTDATA_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "testdata", "knowledge_base"
)

KB_ID = "kb_formats"

# Every format V1 accepts, with a phrase that only survives if the file was really parsed rather
# than read as bytes: the PDF stream, the docx zip and the rich-text JSON are all unreadable as
# plain text, so an assertion on their prose is an assertion that the right reader ran.
ACCEPTED_FIXTURES = {
    "samples.txt": "laboratory information system",
    "pipeline.md": "aligns reads against the reference genome",
    "assay_report.pdf": "cluster density fell below the acceptance threshold",
    "culture_sop.docx": "thirty-seven degrees Celsius",
    "changelog.html": "incremental export driven by a content hash",
    "freezer_note.json": "Aliquots leave the cryostorage freezer on dry ice",
    "calibration_space_note.json": "recalibrated against the blank buffer",
}

# The reason each rejected format is rejected has to reach the user, so every entry names the word
# the message must contain.
REJECTED_FIXTURES = {
    "measurements.csv": "tabular",
    "measurements.xlsx": "tabular",
    "instrument_readings.json": "rich-text",
    "legacy_report.doc": ".docx",
}


class TestKnowledgeBaseDocumentLoader(TestCase):
    """Tests for the format coverage of the knowledge-base document loader.

    Nothing here touches the engine, LanceDB or an embedding: the loader's whole job is turning a
    file into text plus the four chunk metadata keys, and that is what is asserted.
    """

    temp_dir: str

    def setUp(self) -> None:
        self.temp_dir = tempfile.mkdtemp(prefix="kb_loader_test_")

    def tearDown(self) -> None:
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    ############################################### HELPERS ###############################################

    @staticmethod
    def _testdata_path(filename: str) -> str:
        return os.path.join(TESTDATA_DIR, filename)

    def _load_text(self, filename: str) -> str:
        documents = DocumentLoader.load(
            path=self._testdata_path(filename),
            knowledge_base_id=KB_ID,
            document_id="doc_1",
            filename=filename,
        )
        self.assertEqual(len(documents), 1)
        return documents[0].text

    ############################################### ACCEPTED FORMATS ###############################################

    def test_every_accepted_format_yields_its_prose(self):
        for filename, expected_phrase in ACCEPTED_FIXTURES.items():
            with self.subTest(filename=filename):
                self.assertIn(expected_phrase, self._load_text(filename))

    def test_pdf_pages_are_joined_into_one_document(self):
        text = self._load_text("assay_report.pdf")

        self.assertIn("Sequencing assay report", text)
        self.assertIn("second flow cell passed every quality gate", text)

    def test_docx_paragraphs_are_kept_in_order(self):
        text = self._load_text("culture_sop.docx")

        self.assertLess(
            text.index("Cell culture standard operating procedure"),
            text.index("Passage the culture once confluence"),
        )

    def test_html_keeps_the_prose_and_drops_markup_script_and_style(self):
        """Script and style bodies are text to a byte reader and noise to an embedding."""
        text = self._load_text("changelog.html")

        self.assertIn("Analysis platform changelog", text)
        self.assertIn("The plate reader importer now accepts multi-well layouts.", text)
        self.assertNotIn("<h1>", text)
        self.assertNotIn("console.log", text)
        self.assertNotIn("font-family", text)

    def test_rich_text_json_is_converted_to_markdown(self):
        text = self._load_text("freezer_note.json")

        self.assertIn("Freezer transfer note", text)
        self.assertIn("Rack twelve holds the reserved aliquots", text)
        # Markdown, not the raw JSON: no editor block plumbing reaches the embedding.
        self.assertNotIn('"blocks"', text)
        self.assertNotIn("editorVersion", text)

    def test_rich_text_aggregate_json_is_converted_to_markdown(self):
        """A space note arrives wrapped in a RichTextAggregateDTO rather than as a bare rich text."""
        text = self._load_text("calibration_space_note.json")

        self.assertIn("Instrument calibration log", text)
        self.assertNotIn('"richText"', text)

    def test_every_accepted_format_carries_only_the_chunk_metadata(self):
        """A reader that smuggles in its own keys (PDFReader adds a page label) would leak them
        into the embedded and LLM text, since only the four known keys are excluded."""
        for filename in ACCEPTED_FIXTURES:
            with self.subTest(filename=filename):
                documents = DocumentLoader.load(
                    path=self._testdata_path(filename),
                    knowledge_base_id=KB_ID,
                    document_id="doc_1",
                    filename=filename,
                )
                document = documents[0]

                self.assertEqual(
                    set(document.metadata),
                    {
                        METADATA_KNOWLEDGE_BASE_ID,
                        METADATA_DOCUMENT_ID,
                        METADATA_FILENAME,
                        METADATA_ACCESS_SCOPE,
                    },
                )
                for metadata_mode in (MetadataMode.EMBED, MetadataMode.LLM):
                    content = document.get_content(metadata_mode=metadata_mode)
                    self.assertNotIn(KB_ID, content)
                    self.assertNotIn("doc_1", content)
                    self.assertNotIn(filename, content)

    def test_the_filename_decides_the_format_not_the_snapshot_path(self):
        """Snapshots are stored under a sanitised name, so the original filename is the authority."""
        snapshot_path = os.path.join(self.temp_dir, "doc_1_snapshot")
        shutil.copyfile(self._testdata_path("changelog.html"), snapshot_path)

        documents = DocumentLoader.load(
            path=snapshot_path,
            knowledge_base_id=KB_ID,
            document_id="doc_1",
            filename="changelog.html",
        )

        self.assertNotIn("<h1>", documents[0].text)
        self.assertIn("Analysis platform changelog", documents[0].text)

    ############################################### REJECTED FORMATS ###############################################

    def test_every_rejected_format_names_its_reason_and_what_is_supported(self):
        for filename, expected_reason_word in REJECTED_FIXTURES.items():
            with self.subTest(filename=filename):
                with self.assertRaises(UnsupportedDocumentFormatError) as context:
                    DocumentLoader.load(
                        path=self._testdata_path(filename),
                        knowledge_base_id=KB_ID,
                        document_id="doc_1",
                        filename=filename,
                    )

                message = str(context.exception)
                self.assertIn(expected_reason_word, message)
                # Naming the reason is not enough on its own: the user also needs the way out.
                self.assertIn(".pdf", message)
                self.assertIn(".md", message)

    def test_tabular_rejection_explains_the_retrieval_cost(self):
        """Rejecting tables is a decision, so the message has to carry the decision, not a shrug."""
        with self.assertRaises(UnsupportedDocumentFormatError) as context:
            DocumentLoader.load(
                path=self._testdata_path("measurements.csv"),
                knowledge_base_id=KB_ID,
                document_id="doc_1",
                filename="measurements.csv",
            )

        message = str(context.exception).lower()
        self.assertIn("row", message)
        self.assertIn("retrieval", message)

    def test_a_file_with_no_extension_is_rejected(self):
        no_extension_path = os.path.join(self.temp_dir, "readme")
        with open(no_extension_path, "w", encoding="utf-8") as file:
            file.write("some prose")

        with self.assertRaises(UnsupportedDocumentFormatError):
            DocumentLoader.load(
                path=no_extension_path,
                knowledge_base_id=KB_ID,
                document_id="doc_1",
                filename="readme",
            )

    def test_malformed_json_is_rejected_rather_than_crashing(self):
        broken_path = os.path.join(self.temp_dir, "broken.json")
        with open(broken_path, "w", encoding="utf-8") as file:
            file.write("{not json at all")

        with self.assertRaises(UnsupportedDocumentFormatError) as context:
            DocumentLoader.load(
                path=broken_path,
                knowledge_base_id=KB_ID,
                document_id="doc_1",
                filename="broken.json",
            )

        # A JSONDecodeError escaping here would surface as an opaque failure instead of a rejection.
        self.assertIn("rich-text", str(context.exception))

    def test_a_document_yielding_no_text_is_refused_rather_than_indexed_empty(self):
        """A scanned PDF is the real case: a supported format its reader extracts nothing from.

        Without this guard the document indexes to zero chunks and is recorded as done — a
        permanently unretrievable document that reports success.
        """
        empty_path = os.path.join(self.temp_dir, "scanned.md")
        with open(empty_path, "w", encoding="utf-8") as file:
            file.write("   \n\n  ")

        with self.assertRaises(EmptyDocumentError) as context:
            DocumentLoader.load(
                path=empty_path,
                knowledge_base_id=KB_ID,
                document_id="doc_1",
                filename="scanned.md",
            )

        self.assertIn("scanned.md", str(context.exception))

    def test_htm_is_read_as_html(self):
        """``.htm`` is accepted alongside ``.html``, and must reach the same reader."""
        htm_path = os.path.join(self.temp_dir, "changelog.htm")
        shutil.copyfile(self._testdata_path("changelog.html"), htm_path)

        documents = DocumentLoader.load(
            path=htm_path,
            knowledge_base_id=KB_ID,
            document_id="doc_1",
            filename="changelog.htm",
        )

        self.assertIn("Analysis platform changelog", documents[0].text)
        self.assertNotIn("<h1>", documents[0].text)

    def test_every_tabular_extension_is_rejected_for_the_same_reason(self):
        """The spreadsheet family beyond the two fixtures, rejected by extension alone."""
        for extension in (".tsv", ".xls", ".xlsm"):
            with self.subTest(extension=extension):
                with self.assertRaises(UnsupportedDocumentFormatError) as context:
                    DocumentLoader.check_extension_is_supported(extension)

                self.assertIn("tabular", str(context.exception))

    def test_the_snapshot_path_extension_is_the_fallback_when_the_filename_has_none(self):
        """A fetched copy can carry the extension a source-provided name lacks."""
        snapshot_path = os.path.join(self.temp_dir, "fetched_copy.md")
        shutil.copyfile(self._testdata_path("pipeline.md"), snapshot_path)

        documents = DocumentLoader.load(
            path=snapshot_path,
            knowledge_base_id=KB_ID,
            document_id="doc_1",
            filename="pipeline",
        )

        self.assertIn("aligns reads against the reference genome", documents[0].text)

    def test_a_missing_file_raises_file_not_found(self):
        with self.assertRaises(FileNotFoundError):
            DocumentLoader.load(
                path=os.path.join(self.temp_dir, "absent.md"),
                knowledge_base_id=KB_ID,
                document_id="doc_1",
                filename="absent.md",
            )


class TestKnowledgeBaseDocumentCompatibility(TestCase):
    """Tests for the add-time admission check.

    It runs on the *fetched* file, so it knows nothing about the source that produced it: an upload,
    a lab resource and a provider from another brick all pass through the same two rules plus the
    rich-text JSON check.
    """

    temp_dir: str

    def setUp(self) -> None:
        self.temp_dir = tempfile.mkdtemp(prefix="kb_compat_test_")

    def tearDown(self) -> None:
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    @staticmethod
    def _testdata_path(filename: str) -> str:
        return os.path.join(TESTDATA_DIR, filename)

    def test_every_accepted_format_is_compatible(self):
        for filename in ACCEPTED_FIXTURES:
            with self.subTest(filename=filename):
                DocumentCompatibility.check_file_is_compatible(
                    self._testdata_path(filename), filename
                )

    def test_every_rejected_format_is_refused_at_add_time(self):
        for filename, expected_reason_word in REJECTED_FIXTURES.items():
            with self.subTest(filename=filename):
                path = self._testdata_path(filename)

                with self.assertRaises(UnsupportedDocumentFormatError) as context:
                    DocumentCompatibility.check_file_is_compatible(path, filename)

                self.assertIn(expected_reason_word, str(context.exception))

    def test_data_json_is_refused_before_anything_is_indexed(self):
        """The extension alone cannot tell a note from a data dump, so the shape is inspected."""
        path = self._testdata_path("instrument_readings.json")

        with self.assertRaises(UnsupportedDocumentFormatError) as context:
            DocumentCompatibility.check_file_is_compatible(path, "instrument_readings.json")

        message = str(context.exception)
        self.assertIn(".json", message)
        self.assertIn("rich-text", message)

    def test_a_file_above_the_size_cap_is_refused_naming_both_sizes(self):
        oversized_path = os.path.join(self.temp_dir, "huge.md")
        with open(oversized_path, "wb") as file:
            file.truncate(MAX_DOCUMENT_SIZE_MB * 1024 * 1024 + 1)

        with self.assertRaises(DocumentTooLargeError) as context:
            DocumentCompatibility.check_file_is_compatible(oversized_path, "huge.md")

        message = str(context.exception)
        self.assertIn(str(MAX_DOCUMENT_SIZE_MB), message)
        self.assertIn("huge.md", message)

    def test_a_file_exactly_at_the_size_cap_is_accepted(self):
        """The cap is inclusive, so a file sized exactly at it must not be refused."""
        at_cap_path = os.path.join(self.temp_dir, "at_cap.md")
        with open(at_cap_path, "wb") as file:
            file.truncate(MAX_DOCUMENT_SIZE_MB * 1024 * 1024)

        DocumentCompatibility.check_file_is_compatible(at_cap_path, "at_cap.md")

    def test_the_size_cap_applies_whatever_the_format(self):
        """The check is generic: a rich-text note over the cap is refused like any other file."""
        with open(self._testdata_path("freezer_note.json"), encoding="utf-8") as file:
            note = json.load(file)

        oversized_note_path = os.path.join(self.temp_dir, "huge_note.json")
        with open(oversized_note_path, "w", encoding="utf-8") as file:
            json.dump(note, file)
            file.write(" " * (MAX_DOCUMENT_SIZE_MB * 1024 * 1024))

        with self.assertRaises(DocumentTooLargeError):
            DocumentCompatibility.check_file_is_compatible(oversized_note_path, "huge_note.json")

    def test_a_missing_file_is_not_compatible(self):
        absent_path = os.path.join(self.temp_dir, "absent.md")

        with self.assertRaises(FileNotFoundError):
            DocumentCompatibility.check_file_is_compatible(absent_path, "absent.md")
