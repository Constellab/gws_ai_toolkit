"""The ``resource`` document source, against real lab resources.

Everything here runs on resources really saved in the lab's file store and really tagged, because the
parts worth testing are exactly the parts a fake would have to invent: which resources the tag search
returns (and which it must not — an untagged one, an archived one, a resource that is not a file), that
a fetch hands back a *copy* rather than the resource's own file, and that a note becomes Markdown
before it is snapshotted.

The bulk import is covered end to end here too, on the same real resources: the provider-agnostic half
of ``import_documents`` is tested against a fake source in ``test_knowledge_base_service.py``, so what
this file adds is that the two halves fit together — tag in, indexed documents out, and **no
bookkeeping tag written back to the resource**.

Indexing runs on the deterministic ``mock`` embedding, so nothing calls an API.
"""

import os
import shutil
import tempfile
from unittest.mock import patch

from gws_ai_toolkit.models.knowledge_base.embedding_manifest_model import EmbeddingManifestModel
from gws_ai_toolkit.models.knowledge_base.knowledge_base import KnowledgeBase
from gws_ai_toolkit.models.knowledge_base.knowledge_base_document import KnowledgeBaseDocument
from gws_ai_toolkit.models.knowledge_base.knowledge_base_dto import (
    DocumentIndexStatus,
    ImportReport,
    ImportSkipReason,
    SaveKnowledgeBaseDTO,
)
from gws_ai_toolkit.models.knowledge_base.knowledge_base_service import KnowledgeBaseService
from gws_ai_toolkit.rag.common.rag_resource import RagResource
from gws_ai_toolkit.rag.knowledge_base.document_loader import UnsupportedDocumentFormatError
from gws_ai_toolkit.rag.knowledge_base.knowledge_base_config import EmbeddingConfig
from gws_ai_toolkit.rag.knowledge_base.knowledge_base_engine import KnowledgeBaseEngine
from gws_ai_toolkit.rag.knowledge_base.knowledge_base_storage import KnowledgeBaseStorage
from gws_ai_toolkit.rag.knowledge_base.sources.knowledge_base_source import (
    DocumentSourceOperationNotSupportedError,
    KnowledgeBaseDocumentSourceRegistry,
    SourceOpenActionType,
    compute_bytes_content_hash,
)
from gws_ai_toolkit.rag.knowledge_base.sources.resource_source import (
    RESOURCE_SOURCE_TYPE,
    TAG_KEY_CRITERION,
    TAG_VALUE_CRITERION,
    ResourceDocumentSource,
)
from gws_core import (
    BaseTestCase,
    EntityTagList,
    File,
    FsNodeService,
    ResourceModel,
    ResourceOrigin,
    Table,
    Tag,
    TagEntityType,
    TagService,
)

TESTDATA_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "testdata", "knowledge_base"
)

IMPORT_TAG_KEY = "knowledge_base"
IMPORT_TAG_VALUE = "protocols"

MARKDOWN_CONTENT = (
    "# Sequencing pipeline\n\n"
    "The alignment step aligns reads against the reference genome, then marks duplicates.\n"
)


# test_knowledge_base_resource_source
class TestKnowledgeBaseResourceSource(BaseTestCase):
    """The lab-resource provider, and a tag import running on it."""

    source: ResourceDocumentSource
    service: KnowledgeBaseService
    temp_dir: str

    def setUp(self) -> None:
        super().setUp()
        # BaseTestCase truncates once per class, so rows of a previous test method would collide with
        # this one: knowledge-base names are unique, and — the reason the resources go too — a tag
        # search is global, so another method's tagged resources would show up as candidates here, and
        # the file store would rename a second ``protocol.md`` to ``protocol_1.md``.
        KnowledgeBaseDocument.delete().execute()
        KnowledgeBase.delete().execute()
        EmbeddingManifestModel.delete().execute()
        for resource_model in list(ResourceModel.select()):
            # Takes the tags and the stored file with it, which is what makes the next method's
            # resources look like the first ones ever created.
            resource_model.delete_instance()

        self.temp_dir = tempfile.mkdtemp(prefix="kb_resource_source_test_")
        self._base_dir_patch = patch.object(
            KnowledgeBaseStorage, "get_base_dir", return_value=self.temp_dir
        )
        self._base_dir_patch.start()

        self.source = ResourceDocumentSource()
        self.service = KnowledgeBaseService()

    def tearDown(self) -> None:
        self._base_dir_patch.stop()
        shutil.rmtree(self.temp_dir, ignore_errors=True)
        super().tearDown()

    ############################################### HELPERS ###############################################

    def _create_file_resource(self, filename: str, content: str) -> ResourceModel:
        """A ``File`` resource holding this content, saved in the lab's file store."""
        staging_dir = tempfile.mkdtemp(dir=self.temp_dir)
        path = os.path.join(staging_dir, filename)
        with open(path, "w", encoding="utf-8") as file:
            file.write(content)
        return FsNodeService.create_fs_node_model(File(path))

    def _create_resource_from_fixture(self, fixture_name: str) -> ResourceModel:
        """A ``File`` resource holding one of the loader's own test fixtures."""
        staging_dir = tempfile.mkdtemp(dir=self.temp_dir)
        path = os.path.join(staging_dir, fixture_name)
        shutil.copyfile(os.path.join(TESTDATA_DIR, fixture_name), path)
        return FsNodeService.create_fs_node_model(File(path))

    @staticmethod
    def _tag(resource_model: ResourceModel, value: str = IMPORT_TAG_VALUE) -> None:
        TagService.add_tag_to_entity(
            TagEntityType.RESOURCE, resource_model.id, Tag(IMPORT_TAG_KEY, value)
        )

    def _list_by_tag(self, tag_value: str = IMPORT_TAG_VALUE) -> list[str]:
        """The source ids the tag search returns, for the assertions to compare as sets."""
        candidates = self.source.list_documents(
            {TAG_KEY_CRITERION: IMPORT_TAG_KEY, TAG_VALUE_CRITERION: tag_value}
        )
        return [candidate.source_id for candidate in candidates]

    def _build_engine(self, instance_scope: str = "default") -> KnowledgeBaseEngine:
        return KnowledgeBaseService.build_engine(
            instance_scope=instance_scope, embedding_config=EmbeddingConfig.mock()
        )

    def _import_by_tag(
        self, knowledge_base: KnowledgeBase, engine: KnowledgeBaseEngine
    ) -> ImportReport:
        return self.service.import_documents(
            knowledge_base_id=knowledge_base.id,
            source_type=RESOURCE_SOURCE_TYPE,
            criteria={TAG_KEY_CRITERION: IMPORT_TAG_KEY, TAG_VALUE_CRITERION: IMPORT_TAG_VALUE},
            engine=engine,
        )

    ############################################### REGISTRATION ###############################################

    def test_the_resource_source_is_registered_in_production(self):
        registered = KnowledgeBaseDocumentSourceRegistry.get(RESOURCE_SOURCE_TYPE)

        self.assertIsInstance(registered, ResourceDocumentSource)

    ############################################### TAG SEARCH ###############################################

    def test_the_tag_search_returns_the_tagged_file_resources_only(self):
        tagged = self._create_file_resource("protocol.md", MARKDOWN_CONTENT)
        self._tag(tagged)
        # Tagged but not a file: no fetch could ever produce a document from it.
        tagged_table = ResourceModel.save_from_resource(Table(), origin=ResourceOrigin.UPLOADED)
        self._tag(tagged_table)
        # A file, but nobody asked for it.
        self._create_file_resource("unrelated.md", MARKDOWN_CONTENT)
        # Tagged, a file, and put away by its owner.
        archived = self._create_file_resource("old.md", MARKDOWN_CONTENT)
        self._tag(archived)
        archived.archive(True)

        self.assertEqual(self._list_by_tag(), [tagged.id])

    def test_the_tag_search_lists_an_incompatible_file_and_lets_the_import_refuse_it(self):
        """Enumeration is a search, not an admission check: the reason belongs in the report."""
        spreadsheet = self._create_resource_from_fixture("measurements.csv")
        self._tag(spreadsheet)

        self.assertEqual(self._list_by_tag(), [spreadsheet.id])

    def test_an_empty_tag_value_matches_every_value_of_that_key(self):
        protocols = self._create_file_resource("protocol.md", MARKDOWN_CONTENT)
        self._tag(protocols, "protocols")
        reports = self._create_file_resource("report.md", MARKDOWN_CONTENT)
        self._tag(reports, "reports")

        source_ids = self.source.list_documents(
            {TAG_KEY_CRITERION: IMPORT_TAG_KEY, TAG_VALUE_CRITERION: ""}
        )

        self.assertEqual(
            sorted(candidate.source_id for candidate in source_ids),
            sorted([protocols.id, reports.id]),
        )
        # And a value narrows it back down.
        self.assertEqual(self._list_by_tag("reports"), [reports.id])

    def test_a_criterion_with_no_tag_key_is_refused(self):
        """Every resource in the lab would otherwise be a candidate."""
        with self.assertRaises(ValueError):
            self.source.list_documents({TAG_VALUE_CRITERION: IMPORT_TAG_VALUE})

    def test_a_candidate_carries_the_resource_name(self):
        resource_model = self._create_file_resource("protocol.md", MARKDOWN_CONTENT)
        self._tag(resource_model)

        candidates = self.source.list_documents(
            {TAG_KEY_CRITERION: IMPORT_TAG_KEY, TAG_VALUE_CRITERION: IMPORT_TAG_VALUE}
        )

        self.assertEqual(candidates[0].filename, "protocol.md")

    ############################################### FETCH ###############################################

    def test_fetch_hands_back_a_copy_and_the_hash_of_its_content(self):
        """A copy, not the resource's own file: the service deletes what it is handed."""
        resource_model = self._create_file_resource("protocol.md", MARKDOWN_CONTENT)
        resource_path = resource_model.get_resource().path

        fetched = self.source.fetch_file(resource_model.id, None)

        self.assertNotEqual(fetched.path, resource_path)
        self.assertEqual(fetched.filename, "protocol.md")
        with open(fetched.path, encoding="utf-8") as copy:
            self.assertEqual(copy.read(), MARKDOWN_CONTENT)
        self.assertEqual(
            fetched.version_marker, compute_bytes_content_hash(MARKDOWN_CONTENT.encode("utf-8"))
        )

        # Deleting the fetched copy, as the service does, leaves the lab resource alone.
        os.remove(fetched.path)
        self.assertTrue(os.path.isfile(resource_path))

    def test_fetch_converts_a_rich_text_note_to_markdown(self):
        """The snapshot is what a user downloads and what AI Expert reads; editor JSON is not that."""
        resource_model = self._create_resource_from_fixture("freezer_note.json")

        fetched = self.source.fetch_file(resource_model.id, None)

        self.assertTrue(fetched.filename.endswith(".md"))
        with open(fetched.path, encoding="utf-8") as converted:
            markdown = converted.read()
        self.assertIn("Freezer transfer note", markdown)
        self.assertNotIn('"blocks"', markdown)
        # The marker is the hash of the converted bytes, so it follows the note's text.
        self.assertEqual(
            fetched.version_marker, compute_bytes_content_hash(markdown.encode("utf-8"))
        )

    def test_fetching_an_incompatible_format_is_refused_with_the_reason(self):
        resource_model = self._create_resource_from_fixture("measurements.csv")

        with self.assertRaises(UnsupportedDocumentFormatError) as context:
            self.source.fetch_file(resource_model.id, None)

        self.assertIn("tabular", str(context.exception))

    def test_fetching_a_resource_that_is_not_a_file_is_refused_with_the_reason(self):
        table = ResourceModel.save_from_resource(Table(), origin=ResourceOrigin.UPLOADED)

        with self.assertRaises(DocumentSourceOperationNotSupportedError) as context:
            self.source.fetch_file(table.id, None)

        self.assertIn("not a file", str(context.exception))

    def test_fetching_a_resource_that_no_longer_exists_is_refused_with_the_reason(self):
        with self.assertRaises(DocumentSourceOperationNotSupportedError) as context:
            self.source.fetch_file("no-such-resource", None)

        self.assertIn("no longer exists", str(context.exception))

    ############################################### VERSION MARKER ###############################################

    def test_the_version_marker_matches_the_fetched_hash_and_follows_the_content(self):
        resource_model = self._create_file_resource("protocol.md", MARKDOWN_CONTENT)
        fetched = self.source.fetch_file(resource_model.id, None)

        self.assertEqual(self.source.get_version_marker(resource_model.id, None), fetched.version_marker)

        # The resource is edited in place, as a save from the lab would.
        with open(resource_model.get_resource().path, "w", encoding="utf-8") as file:
            file.write(MARKDOWN_CONTENT + "\nA variant calling step was added.\n")

        self.assertNotEqual(
            self.source.get_version_marker(resource_model.id, None), fetched.version_marker
        )

    def test_the_version_marker_of_a_rich_text_note_is_the_hash_of_its_markdown(self):
        resource_model = self._create_resource_from_fixture("freezer_note.json")
        fetched = self.source.fetch_file(resource_model.id, None)

        self.assertEqual(self.source.get_version_marker(resource_model.id, None), fetched.version_marker)

    def test_the_version_marker_is_none_when_the_resource_cannot_answer(self):
        """``None`` means "unknown", which is what a sync reports and what never breaks a re-index."""
        self.assertIsNone(self.source.get_version_marker("no-such-resource", None))
        self.assertIsNone(self.source.get_version_marker(None, None))
        self.assertIsNone(self.source.get_version_marker(ResourceModel.save_from_resource(Table(), origin=ResourceOrigin.UPLOADED).id, None))

        # Note content that turns out to be data JSON cannot be converted, so it has no marker.
        data_json = self._create_resource_from_fixture("instrument_readings.json")
        self.assertIsNone(self.source.get_version_marker(data_json.id, None))

    ############################################### OPEN ACTION ###############################################

    def test_opening_a_resource_document_goes_through_a_share_link(self):
        knowledge_base = self.service.create_knowledge_base(SaveKnowledgeBaseDTO(name="Protocols"))
        resource_model = self._create_file_resource("protocol.md", MARKDOWN_CONTENT)
        document = self.service.add_document(
            knowledge_base.id, RESOURCE_SOURCE_TYPE, resource_model.id
        )

        action = self.service.get_document_open_action(document)

        self.assertEqual(action.type, SourceOpenActionType.EXTERNAL_LINK)
        self.assertTrue(action.url)

    def test_opening_falls_back_to_the_snapshot_when_no_link_can_be_made(self):
        """The snapshot is the copy that is always there, so a dead resource is still readable."""
        knowledge_base = self.service.create_knowledge_base(SaveKnowledgeBaseDTO(name="Protocols"))
        resource_model = self._create_file_resource("protocol.md", MARKDOWN_CONTENT)
        document = self.service.add_document(
            knowledge_base.id, RESOURCE_SOURCE_TYPE, resource_model.id
        )

        with patch(
            "gws_ai_toolkit.rag.knowledge_base.sources.resource_source.Utils"
            ".generate_temp_share_resource_link",
            side_effect=Exception("the resource is gone"),
        ):
            action = self.service.get_document_open_action(document)

        self.assertEqual(action.type, SourceOpenActionType.DOWNLOAD_SNAPSHOT)

    ############################################### IMPORT BY TAG ###############################################

    def test_importing_by_tag_adds_snapshots_and_indexes_the_tagged_resources(self):
        knowledge_base = self.service.create_knowledge_base(SaveKnowledgeBaseDTO(name="Protocols"))
        protocol = self._create_file_resource("protocol.md", MARKDOWN_CONTENT)
        self._tag(protocol)
        note = self._create_resource_from_fixture("freezer_note.json")
        self._tag(note)
        # Tagged and incompatible: reported, never silently dropped.
        spreadsheet = self._create_resource_from_fixture("measurements.csv")
        self._tag(spreadsheet)
        # Untagged: not a candidate at all.
        self._create_file_resource("unrelated.md", MARKDOWN_CONTENT)
        engine = self._build_engine()

        report = self._import_by_tag(knowledge_base, engine)

        self.assertEqual(len(report.added), 2)
        for added in report.added:
            self.assertEqual(added.index_status, DocumentIndexStatus.DONE.value)
        self.assertEqual([skipped.source_id for skipped in report.skipped], [spreadsheet.id])
        self.assertEqual(report.skipped[0].reason, ImportSkipReason.NOT_INDEXABLE)

        # The note was snapshotted as Markdown, and every document is retrievable.
        documents = self.service.get_documents(knowledge_base.id)
        self.assertEqual(sorted(document.filename for document in documents), ["freezer_note.md", "protocol.md"])
        self.assertTrue(engine.retrieve("reference genome alignment", [knowledge_base.id]))
        self.assertTrue(engine.retrieve("reserved aliquots rack", [knowledge_base.id]))

        # Each row records the criterion it came from.
        for document in documents:
            self.assertEqual(
                document.source_metadata,
                {
                    "imported_from": {
                        TAG_KEY_CRITERION: IMPORT_TAG_KEY,
                        TAG_VALUE_CRITERION: IMPORT_TAG_VALUE,
                    }
                },
            )

    def test_importing_writes_no_bookkeeping_tag_back_to_the_resource(self):
        """Membership lives in the document rows; the lab resource is left exactly as it was."""
        knowledge_base = self.service.create_knowledge_base(SaveKnowledgeBaseDTO(name="Protocols"))
        protocol = self._create_file_resource("protocol.md", MARKDOWN_CONTENT)
        self._tag(protocol)

        self._import_by_tag(knowledge_base, self._build_engine())

        tags = EntityTagList.find_by_entity(TagEntityType.RESOURCE, protocol.id)
        self.assertFalse(tags.has_tag_key(RagResource.RAG_DOC_TAG_KEY))
        self.assertFalse(tags.has_tag_key(RagResource.RAG_DATASET_ID_TAG_KEY))
        self.assertFalse(tags.has_tag_key(RagResource.RAG_SYNC_TAG_KEY))
        # The tag it was imported by is of course still there.
        self.assertTrue(tags.has_tag_key(IMPORT_TAG_KEY))

    def test_importing_the_same_tag_twice_adds_nothing_the_second_time(self):
        knowledge_base = self.service.create_knowledge_base(SaveKnowledgeBaseDTO(name="Protocols"))
        protocol = self._create_file_resource("protocol.md", MARKDOWN_CONTENT)
        self._tag(protocol)
        engine = self._build_engine()

        self._import_by_tag(knowledge_base, engine)
        second = self._import_by_tag(knowledge_base, engine)

        self.assertEqual(second.added, [])
        self.assertEqual([skipped.source_id for skipped in second.skipped], [protocol.id])
        self.assertEqual(second.skipped[0].reason, ImportSkipReason.ALREADY_PRESENT)
        self.assertEqual(len(self.service.get_documents(knowledge_base.id)), 1)

    def test_an_import_never_deletes_a_document_whose_resource_left_the_tag(self):
        knowledge_base = self.service.create_knowledge_base(SaveKnowledgeBaseDTO(name="Protocols"))
        protocol = self._create_file_resource("protocol.md", MARKDOWN_CONTENT)
        self._tag(protocol)
        engine = self._build_engine()
        first = self._import_by_tag(knowledge_base, engine)
        document_id = first.added[0].document_id

        # Untagged, then imported again: reconciliation is a later feature, an import only adds.
        EntityTagList.find_by_entity(TagEntityType.RESOURCE, protocol.id).delete_tags(
            [Tag(IMPORT_TAG_KEY, IMPORT_TAG_VALUE)]
        )
        second = self._import_by_tag(knowledge_base, engine)

        self.assertEqual(second.added, [])
        self.assertEqual(second.skipped, [])
        kept = self.service.get_document_and_check(document_id)
        self.assertEqual(kept.index_status, DocumentIndexStatus.DONE.value)
        self.assertTrue(os.path.isfile(kept.snapshot_path))
        self.assertTrue(engine.retrieve("reference genome alignment", [knowledge_base.id]))

    ############################################### REFRESH ###############################################

    def test_refresh_follows_the_resource_and_only_reindexes_when_it_changed(self):
        """The import → query → modify → refresh → query round trip, hash check included."""
        knowledge_base = self.service.create_knowledge_base(SaveKnowledgeBaseDTO(name="Protocols"))
        protocol = self._create_file_resource("protocol.md", MARKDOWN_CONTENT)
        self._tag(protocol)
        engine = self._build_engine()
        report = self._import_by_tag(knowledge_base, engine)
        document_id = report.added[0].document_id

        # Saved again with no edit: the same hash, so nothing is queued for re-embedding.
        unchanged = self.service.refresh_document(document_id)
        self.assertFalse(unchanged.content_changed)
        self.assertEqual(unchanged.document.index_status, DocumentIndexStatus.DONE.value)

        # Now really edited in the lab.
        with open(protocol.get_resource().path, "w", encoding="utf-8") as file:
            file.write("# Sequencing pipeline\n\nA variant calling step follows the alignment.\n")

        changed = self.service.refresh_document(document_id)

        self.assertTrue(changed.content_changed)
        self.assertEqual(changed.document.index_status, DocumentIndexStatus.PENDING.value)
        self.service.index_document(document_id, engine)

        chunks = engine.retrieve("variant calling step", [knowledge_base.id])
        self.assertTrue(chunks)
        self.assertIn("variant calling", chunks[0].content)
