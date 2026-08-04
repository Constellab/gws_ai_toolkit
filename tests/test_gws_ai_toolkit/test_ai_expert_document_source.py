"""Where AI Expert's two modes get their text from, against the real stack.

The conversation tests drive the loop with a stub retriever and a hand-written snapshot. This file
covers what only the real thing can prove: that a document added to a knowledge base and indexed is
the document AI Expert answers about — its chunks retrieved through the engine with the
``document_ids`` filter, its snapshot read from disk — and that a neighbouring document in the same
knowledge base never reaches the model.

Everything runs on the deterministic ``mock`` embedding and a scripted model, so nothing calls an API.
"""

import shutil
import tempfile
from unittest.mock import patch

from gws_ai_toolkit.core.agents.base_function_agent_events import UserQueryTextEvent
from gws_ai_toolkit.models.chat.conversation.ai_expert_agent_ai import AiExpertAgentAi
from gws_ai_toolkit.models.chat.conversation.ai_expert_chat_config import AiExpertChatConfig
from gws_ai_toolkit.models.chat.conversation.ai_expert_document import AiExpertDocument
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

from .agent_test_helper import SingleAgentScriptedModel

ALIGNMENT_CONTENT = (
    "# Sequencing pipeline\n\n"
    "The alignment step aligns reads against the reference genome, then marks duplicates.\n"
)
SAFETY_CONTENT = (
    "# Laboratory safety\n\n"
    "Gloves and goggles are mandatory when handling the reagents of the assay.\n"
)


# test_ai_expert_document_source
class TestAiExpertDocumentSource(BaseTestCase):
    """AI Expert against a really indexed document, in both modes."""

    service: KnowledgeBaseService
    temp_dir: str

    def setUp(self) -> None:
        super().setUp()
        # BaseTestCase truncates once per class, so rows of a previous test method would collide with
        # this one (knowledge-base names are unique).
        KnowledgeBaseDocument.delete().execute()
        KnowledgeBase.delete().execute()
        EmbeddingManifestModel.delete().execute()

        self.temp_dir = tempfile.mkdtemp(prefix="ai_expert_source_test_")
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

    def _index_document(
        self, knowledge_base: KnowledgeBase, content: str, filename: str
    ) -> KnowledgeBaseDocument:
        """One indexed document of a knowledge base, snapshot written and chunks in the store."""
        document = self.service.add_uploaded_document(
            knowledge_base.id, filename, content.encode("utf-8")
        )
        engine = KnowledgeBaseService.build_engine(
            instance_scope=knowledge_base.instance_scope, embedding_config=EmbeddingConfig.mock()
        )
        return self.service.index_document(document.id, engine)

    def _build_agent(
        self, document: KnowledgeBaseDocument, mode: str, answer: str = "An answer."
    ) -> tuple[AiExpertAgentAi, SingleAgentScriptedModel]:
        """An agent answering about this document, through the real engine."""
        scripted_model = SingleAgentScriptedModel(turns=[answer])
        agent = AiExpertAgentAi(
            chat_config=AiExpertChatConfig(mode=mode, max_chunks=5),
            document=AiExpertDocument.from_document(document),
            retriever=EngineKnowledgeBaseRetriever(EmbeddingConfig.mock()),
            model=scripted_model.build(),
        )
        return agent, scripted_model

    @staticmethod
    def _ask(agent: AiExpertAgentAi, question: str) -> None:
        """Run one turn, draining the event stream."""
        list(agent.call_agent(UserQueryTextEvent(query=question, agent_id=agent.id)))

    ############################################### TESTS ###############################################

    def test_relevant_chunks_reads_the_chunks_of_that_document_only(self):
        """The retrieval is filtered to the opened document, inside its knowledge base."""
        knowledge_base = self.service.create_knowledge_base(SaveKnowledgeBaseDTO(name="Protocols"))
        alignment = self._index_document(knowledge_base, ALIGNMENT_CONTENT, "pipeline.md")
        self._index_document(knowledge_base, SAFETY_CONTENT, "safety.md")

        agent, scripted_model = self._build_agent(alignment, mode="relevant_chunks")
        # A question whose words appear in the *other* document of the same knowledge base.
        self._ask(agent, "are gloves and goggles mandatory?")

        instructions = scripted_model.instructions_seen[0]
        self.assertIn("pipeline.md", instructions)
        self.assertNotIn("Gloves and goggles", instructions)

    def test_relevant_chunks_retrieves_the_passages_matching_the_question(self):
        """The document's own content reaches the model when the question matches it."""
        knowledge_base = self.service.create_knowledge_base(SaveKnowledgeBaseDTO(name="Protocols"))
        alignment = self._index_document(knowledge_base, ALIGNMENT_CONTENT, "pipeline.md")

        agent, scripted_model = self._build_agent(alignment, mode="relevant_chunks")
        self._ask(agent, "what does the alignment step do?")

        self.assertIn("aligns reads against the reference genome", scripted_model.instructions_seen[0])

    def test_full_text_chunk_reads_the_snapshot_of_that_document(self):
        """The snapshot written on add is the text, exactly, and no other document's."""
        knowledge_base = self.service.create_knowledge_base(SaveKnowledgeBaseDTO(name="Protocols"))
        alignment = self._index_document(knowledge_base, ALIGNMENT_CONTENT, "pipeline.md")
        self._index_document(knowledge_base, SAFETY_CONTENT, "safety.md")

        agent, scripted_model = self._build_agent(alignment, mode="full_text_chunk")
        self._ask(agent, "summarise this document")

        instructions = scripted_model.instructions_seen[0]
        self.assertIn(ALIGNMENT_CONTENT.strip(), instructions)
        self.assertNotIn("Gloves and goggles", instructions)

    def test_a_document_of_another_knowledge_base_is_not_answered_from(self):
        """The knowledge-base scope holds even though the document id is the narrower filter."""
        protocols = self.service.create_knowledge_base(SaveKnowledgeBaseDTO(name="Protocols"))
        alignment = self._index_document(protocols, ALIGNMENT_CONTENT, "pipeline.md")

        # The same document row, but pointed at a knowledge base it does not belong to.
        document = AiExpertDocument.from_document(alignment)
        document.knowledge_base_id = "kb-that-holds-nothing"

        scripted_model = SingleAgentScriptedModel(turns=["An answer."])
        agent = AiExpertAgentAi(
            chat_config=AiExpertChatConfig(mode="relevant_chunks"),
            document=document,
            retriever=EngineKnowledgeBaseRetriever(EmbeddingConfig.mock()),
            model=scripted_model.build(),
        )
        self._ask(agent, "what does the alignment step do?")

        self.assertNotIn(
            "aligns reads against the reference genome", scripted_model.instructions_seen[0]
        )
