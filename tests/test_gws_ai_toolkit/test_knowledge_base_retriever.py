"""The retrieval seam the chat loop calls, against real indexed content.

The conversation tests drive the loop with a stub retriever; this file covers what the real one adds
on top of the engine: it searches every instance holding one of the requested knowledge bases, merges
what they return, and survives a knowledge base disappearing under a live conversation. Everything
runs on the deterministic ``mock`` embedding, so nothing calls an API.
"""

import shutil
import tempfile
from unittest.mock import patch

from gws_ai_toolkit.models.knowledge_base.embedding_manifest_model import EmbeddingManifestModel
from gws_ai_toolkit.models.knowledge_base.knowledge_base import KnowledgeBase
from gws_ai_toolkit.models.knowledge_base.knowledge_base_document import KnowledgeBaseDocument
from gws_ai_toolkit.models.knowledge_base.knowledge_base_dto import SaveKnowledgeBaseDTO
from gws_ai_toolkit.models.knowledge_base.knowledge_base_retriever import (
    EngineKnowledgeBaseRetriever,
)
from gws_ai_toolkit.models.knowledge_base.knowledge_base_service import KnowledgeBaseService
from gws_ai_toolkit.rag.knowledge_base.knowledge_base_config import EmbeddingConfig
from gws_ai_toolkit.rag.knowledge_base.knowledge_base_storage import KnowledgeBaseStorage
from gws_core import BaseTestCase

ALIGNMENT_CONTENT = (
    "# Sequencing pipeline\n\n"
    "The alignment step aligns reads against the reference genome, then marks duplicates.\n"
)
SAFETY_CONTENT = (
    "# Laboratory safety\n\n"
    "Gloves and goggles are mandatory when handling the reagents of the assay.\n"
)


# test_knowledge_base_retriever
class TestKnowledgeBaseRetriever(BaseTestCase):
    """``EngineKnowledgeBaseRetriever``: scoping, fan-out across instances, dangling bindings."""

    service: KnowledgeBaseService
    temp_dir: str

    def setUp(self) -> None:
        super().setUp()
        # BaseTestCase truncates once per class, so rows of a previous test method would collide
        # with this one (knowledge-base names are unique).
        KnowledgeBaseDocument.delete().execute()
        KnowledgeBase.delete().execute()
        EmbeddingManifestModel.delete().execute()

        self.temp_dir = tempfile.mkdtemp(prefix="kb_retriever_test_")
        self._base_dir_patch = patch.object(
            KnowledgeBaseStorage, "get_base_dir", return_value=self.temp_dir
        )
        self._base_dir_patch.start()

        self.service = KnowledgeBaseService()

    def tearDown(self) -> None:
        self._base_dir_patch.stop()
        shutil.rmtree(self.temp_dir, ignore_errors=True)
        super().tearDown()

    ############################################### HELPERS ###############################################

    def _build_retriever(self) -> EngineKnowledgeBaseRetriever:
        return EngineKnowledgeBaseRetriever(EmbeddingConfig.mock())

    def _create_indexed_knowledge_base(
        self, name: str, content: str, filename: str, instance_scope: str = "default"
    ) -> KnowledgeBase:
        """A knowledge base holding one indexed document, in the given instance."""
        knowledge_base = self.service.create_knowledge_base(
            SaveKnowledgeBaseDTO(name=name, instance_scope=instance_scope)
        )
        self._add_indexed_document(knowledge_base, content, filename)
        return knowledge_base

    def _add_indexed_document(
        self, knowledge_base: KnowledgeBase, content: str, filename: str
    ) -> KnowledgeBaseDocument:
        """One more indexed document in an existing knowledge base."""
        document = self.service.add_uploaded_document(
            knowledge_base.id, filename, content.encode("utf-8")
        )
        engine = KnowledgeBaseService.build_engine(
            instance_scope=knowledge_base.instance_scope, embedding_config=EmbeddingConfig.mock()
        )
        self.service.index_document(document.id, engine)
        return document

    ############################################### TESTS ###############################################

    def test_retrieval_is_scoped_to_the_requested_knowledge_bases(self):
        """The binding is the filter: content of an unrequested knowledge base never comes back."""
        alignment = self._create_indexed_knowledge_base(
            "Protocols", ALIGNMENT_CONTENT, "pipeline.md"
        )
        self._create_indexed_knowledge_base("Safety", SAFETY_CONTENT, "safety.md")

        chunks = self._build_retriever().retrieve(
            query="gloves and goggles", knowledge_base_ids=[alignment.id]
        )

        self.assertTrue(chunks, "the requested knowledge base still answers the query")
        self.assertEqual({chunk.knowledge_base_id for chunk in chunks}, {alignment.id})

    def test_an_empty_binding_retrieves_nothing(self):
        """A profile bound to nothing must search nothing, not everything."""
        self._create_indexed_knowledge_base("Protocols", ALIGNMENT_CONTENT, "pipeline.md")

        self.assertEqual(self._build_retriever().retrieve("alignment", []), [])

    def test_knowledge_bases_of_several_instances_are_searched_together(self):
        """An instance is a separate vector space, so a bound set may span more than one engine."""
        alignment = self._create_indexed_knowledge_base(
            "Protocols", ALIGNMENT_CONTENT, "pipeline.md", instance_scope="default"
        )
        safety = self._create_indexed_knowledge_base(
            "Safety", SAFETY_CONTENT, "safety.md", instance_scope="secondary"
        )

        chunks = self._build_retriever().retrieve(
            query="reads reference genome gloves goggles",
            knowledge_base_ids=[alignment.id, safety.id],
            top_k=10,
        )

        self.assertEqual(
            {chunk.knowledge_base_id for chunk in chunks}, {alignment.id, safety.id}
        )
        # The merged list is ordered, so the model reads the best passage first whichever instance
        # produced it.
        scores = [chunk.score for chunk in chunks]
        self.assertEqual(scores, sorted(scores, reverse=True))

    def test_top_k_caps_the_merged_result_not_each_instance(self):
        """``top_k`` is the number of passages the model sees, not per engine."""
        alignment = self._create_indexed_knowledge_base(
            "Protocols", ALIGNMENT_CONTENT, "pipeline.md", instance_scope="default"
        )
        safety = self._create_indexed_knowledge_base(
            "Safety", SAFETY_CONTENT, "safety.md", instance_scope="secondary"
        )

        chunks = self._build_retriever().retrieve(
            query="alignment gloves",
            knowledge_base_ids=[alignment.id, safety.id],
            top_k=1,
        )

        self.assertEqual(len(chunks), 1)

    def test_a_deleted_knowledge_base_is_dropped_rather_than_raised(self):
        """A binding is a soft reference: a knowledge base deleted later must not break the chat."""
        alignment = self._create_indexed_knowledge_base(
            "Protocols", ALIGNMENT_CONTENT, "pipeline.md"
        )

        chunks = self._build_retriever().retrieve(
            query="alignment step",
            knowledge_base_ids=[alignment.id, "kb-that-no-longer-exists"],
        )

        self.assertTrue(chunks)
        self.assertEqual({chunk.knowledge_base_id for chunk in chunks}, {alignment.id})

    def test_a_binding_pointing_only_at_deleted_knowledge_bases_retrieves_nothing(self):
        """With nothing left to search, the answer is no passage — not every passage."""
        self._create_indexed_knowledge_base("Protocols", ALIGNMENT_CONTENT, "pipeline.md")

        self.assertEqual(
            self._build_retriever().retrieve("alignment", ["gone-1", "gone-2"]), []
        )

    def test_the_retriever_holds_no_engine_between_calls(self):
        """Engines carry a LanceDB connection and a file lock, so none may survive a call."""
        retriever = self._build_retriever()
        knowledge_base = self._create_indexed_knowledge_base(
            "Protocols", ALIGNMENT_CONTENT, "pipeline.md"
        )
        retriever.retrieve("alignment", [knowledge_base.id])

        held = [
            value
            for value in vars(retriever).values()
            if type(value).__name__ == "KnowledgeBaseEngine"
        ]
        self.assertEqual(held, [])

    def test_document_ids_narrow_the_search_to_one_document(self):
        """AI Expert's ``relevant_chunks`` mode: the answer may only quote the document it opened."""
        knowledge_base = self._create_indexed_knowledge_base(
            "Protocols", ALIGNMENT_CONTENT, "pipeline.md"
        )
        safety_document = self._add_indexed_document(knowledge_base, SAFETY_CONTENT, "safety.md")
        retriever = self._build_retriever()

        # Unfiltered, the alignment document answers this query.
        self.assertIn(
            "pipeline.md",
            {chunk.filename for chunk in retriever.retrieve("alignment reads", [knowledge_base.id])},
        )

        chunks = retriever.retrieve(
            query="alignment reads",
            knowledge_base_ids=[knowledge_base.id],
            document_ids=[safety_document.id],
        )

        self.assertEqual({chunk.document_id for chunk in chunks}, {safety_document.id})

    def test_an_empty_document_filter_retrieves_nothing(self):
        """Explicitly narrowing to no document means nothing, as an empty binding does."""
        knowledge_base = self._create_indexed_knowledge_base(
            "Protocols", ALIGNMENT_CONTENT, "pipeline.md"
        )

        self.assertEqual(
            self._build_retriever().retrieve(
                "alignment step", [knowledge_base.id], document_ids=[]
            ),
            [],
        )

    def test_a_document_of_another_knowledge_base_is_still_out_of_scope(self):
        """The document filter narrows *within* the binding rather than replacing it."""
        alignment = self._create_indexed_knowledge_base(
            "Protocols", ALIGNMENT_CONTENT, "pipeline.md"
        )
        safety = self._create_indexed_knowledge_base("Safety", SAFETY_CONTENT, "safety.md")
        safety_document_id = self.service.get_documents(safety.id)[0].id

        chunks = self._build_retriever().retrieve(
            query="gloves and goggles",
            knowledge_base_ids=[alignment.id],
            document_ids=[safety_document_id],
        )

        self.assertEqual(chunks, [])

    def test_the_score_threshold_reaches_the_engine(self):
        """A threshold above every fused score drops everything, which is how it is proved applied."""
        knowledge_base = self._create_indexed_knowledge_base(
            "Protocols", ALIGNMENT_CONTENT, "pipeline.md"
        )
        retriever = self._build_retriever()

        self.assertTrue(retriever.retrieve("alignment step", [knowledge_base.id]))
        # The fused RRF score is rank-derived and never reaches 1.0.
        self.assertEqual(
            retriever.retrieve("alignment step", [knowledge_base.id], score_threshold=1.0), []
        )
