"""Building a knowledge-base chat from a profile, and restoring one from a conversation row.

This is the seam the chat window sits on, and the reason it exists outside Reflex is that the same
two operations are what the future HTTP route needs. What is worth testing here is not the happy
path alone but the four ways a restore legitimately fails — a legacy row, another mode's row, a row
recording no profile, a row whose profile was deleted — because each one must come back as a
sentence a user can read rather than as a stack trace.

No API call is made: an agent holds its model as a string and resolves it only when it runs.
"""

from gws_ai_toolkit.models.chat.chat_conversation import ChatConversation
from gws_ai_toolkit.models.chat.chat_conversation_dto import SaveChatConversationDTO
from gws_ai_toolkit.models.chat.chat_conversation_service import ChatConversationService
from gws_ai_toolkit.models.chat.conversation.base_chat_conversation import (
    LEGACY_CONVERSATION_MODE_MESSAGE,
    ChatConversationMode,
)
from gws_ai_toolkit.models.chat.conversation.knowledge_base_chat_conversation import (
    KnowledgeBaseChatConversation,
)
from gws_ai_toolkit.models.chat.message.chat_message_source import ChatMessageSource
from gws_ai_toolkit.models.chat.message.chat_message_text import ChatMessageText
from gws_ai_toolkit.models.chat.message.chat_message_tool_call import ChatMessageToolCall
from gws_ai_toolkit.models.chat.message.chat_message_tool_result import ChatMessageToolResult
from gws_ai_toolkit.models.chat.message.chat_user_message import ChatUserMessageText
from gws_ai_toolkit.models.knowledge_base.knowledge_base import KnowledgeBase
from gws_ai_toolkit.models.knowledge_base.knowledge_base_agent_ai import (
    SEARCH_KNOWLEDGE_TOOL_NAME,
)
from gws_ai_toolkit.models.knowledge_base.knowledge_base_chat_factory import (
    KnowledgeBaseChatFactory,
    KnowledgeBaseChatUnavailableError,
)
from gws_ai_toolkit.models.knowledge_base.knowledge_base_dto import SaveKnowledgeBaseDTO
from gws_ai_toolkit.models.knowledge_base.knowledge_base_retriever import KnowledgeBaseRetriever
from gws_ai_toolkit.models.knowledge_base.knowledge_base_service import KnowledgeBaseService
from gws_ai_toolkit.models.knowledge_base.rag_chat_profile import RagChatProfile
from gws_ai_toolkit.models.knowledge_base.rag_chat_profile_dto import SaveRagChatProfileDTO
from gws_ai_toolkit.models.knowledge_base.rag_chat_profile_service import RagChatProfileService
from gws_ai_toolkit.models.user.user_sync_service import AiToolkitUserSyncService
from gws_ai_toolkit.rag.knowledge_base.knowledge_base_models import RetrievedChunk
from gws_core import BaseTestCase

from .agent_test_helper import SingleAgentScriptedModel, ToolCall

CHAT_APP_NAME = "test_knowledge_base_chat_factory"


class NoopRetriever(KnowledgeBaseRetriever):
    """A retriever that is never called: most of these tests build conversations without running them."""

    def retrieve(
        self,
        query: str,
        knowledge_base_ids: list[str],
        top_k: int = 5,
        score_threshold: float | None = None,
        document_ids: list[str] | None = None,
    ) -> list[RetrievedChunk]:
        return []


class OneChunkRetriever(KnowledgeBaseRetriever):
    """Answers every search with one passage, recording the queries it was asked for."""

    def __init__(self) -> None:
        self.calls: list[str] = []

    def retrieve(
        self,
        query: str,
        knowledge_base_ids: list[str],
        top_k: int = 5,
        score_threshold: float | None = None,
        document_ids: list[str] | None = None,
    ) -> list[RetrievedChunk]:
        self.calls.append(query)
        return [
            RetrievedChunk(
                chunk_id="chunk-1",
                content="The verification budget is 42000 euros.",
                score=0.03,
                knowledge_base_id="kb-1",
                document_id="doc-1",
                filename="budget.md",
            )
        ]


# test_knowledge_base_chat_factory
class TestKnowledgeBaseChatFactory(BaseTestCase):
    """What a chat window and an HTTP route both do: build a chat, or restore one."""

    @classmethod
    def init_before_test(cls):
        super().init_before_test()
        # The conversation service stamps every row with the current user, which has to exist on the
        # brick's own user table first.
        AiToolkitUserSyncService().sync_all_users()

    def setUp(self) -> None:
        super().setUp()
        # BaseTestCase truncates once per class, so rows from a previous test method would otherwise
        # collide with this one (profile and knowledge-base names are unique).
        RagChatProfile.delete().execute()
        KnowledgeBase.delete().execute()

        self.profile_service = RagChatProfileService()
        self.conversation_service = ChatConversationService()
        self.factory = KnowledgeBaseChatFactory(
            chat_app_name=CHAT_APP_NAME, retriever=NoopRetriever()
        )

    ############################################### HELPERS ###############################################

    def _create_profile(self, name: str = "Support bot", **kwargs) -> RagChatProfile:
        return self.profile_service.create_profile(SaveRagChatProfileDTO(name=name, **kwargs))

    def _create_knowledge_base(self, name: str = "Protocols") -> KnowledgeBase:
        return KnowledgeBaseService().create_knowledge_base(SaveKnowledgeBaseDTO(name=name))

    def _create_conversation_row(
        self, mode: str, configuration: dict, messages: list | None = None
    ) -> ChatConversation:
        return self.conversation_service.save_conversation(
            SaveChatConversationDTO(
                chat_app_name=CHAT_APP_NAME,
                configuration=configuration,
                mode=mode,
                label="A question",
                messages=messages or [],
            )
        )

    ############################################### BUILD ###############################################

    def test_build_conversation_carries_the_profile_into_the_chat(self):
        """The profile's settings reach the agent, and its id reaches the row a restore reads."""
        knowledge_base = self._create_knowledge_base()
        profile = self._create_profile(
            system_prompt="Search first.",
            model="openai:gpt-4.1",
            top_k=3,
            score_threshold=0.02,
            knowledge_base_ids=[knowledge_base.id],
        )

        conversation = self.factory.build_conversation(profile.id)

        self.assertIsInstance(conversation, KnowledgeBaseChatConversation)
        self.assertEqual(conversation.mode, ChatConversationMode.KNOWLEDGE_BASE.value)
        self.assertEqual(
            conversation.chat_configuration[
                KnowledgeBaseChatConversation.CHAT_PROFILE_ID_CONFIG_KEY
            ],
            profile.id,
        )

        chat_config = conversation.knowledge_agent.chat_config
        self.assertEqual(chat_config.chat_profile_id, profile.id)
        self.assertEqual(chat_config.system_prompt, "Search first.")
        self.assertEqual(chat_config.model, "openai:gpt-4.1")
        self.assertEqual(chat_config.top_k, 3)
        self.assertEqual(chat_config.score_threshold, 0.02)
        self.assertEqual(chat_config.knowledge_base_ids, [knowledge_base.id])

    def test_build_conversation_persists_nothing_until_it_is_used(self):
        """Building a chat must not create a conversation row: opening a page is not a conversation."""
        profile = self._create_profile()
        # An existing row, so the chat app exists and the count below is a real count rather than the
        # empty answer the service gives for an unknown chat app.
        self._create_conversation_row(
            mode=ChatConversationMode.KNOWLEDGE_BASE.value,
            configuration={
                KnowledgeBaseChatConversation.CHAT_PROFILE_ID_CONFIG_KEY: profile.id
            },
        )
        # Counted rather than assumed: conversation rows outlive a test method, unlike the profiles
        # and knowledge bases ``setUp`` clears.
        conversations_before = len(
            self.conversation_service.get_all_conversations_by_chat_app(CHAT_APP_NAME)
        )

        conversation = self.factory.build_conversation(profile.id)

        self.assertIsNone(conversation._conversation_id)
        self.assertEqual(
            len(self.conversation_service.get_all_conversations_by_chat_app(CHAT_APP_NAME)),
            conversations_before,
        )

    def test_build_conversation_reports_an_unknown_profile(self):
        with self.assertRaises(KnowledgeBaseChatUnavailableError) as raised:
            self.factory.build_conversation("does-not-exist")

        self.assertIn("does-not-exist", str(raised.exception))

    def test_build_conversation_reports_a_missing_profile_id(self):
        """An empty selection is a configuration the user can fix, not a crash."""
        with self.assertRaises(KnowledgeBaseChatUnavailableError):
            self.factory.build_conversation("")

    ############################################### RESTORE ###############################################

    def test_restore_conversation_reopens_it_on_its_own_profile(self):
        profile = self._create_profile()
        row = self._create_conversation_row(
            mode=ChatConversationMode.KNOWLEDGE_BASE.value,
            configuration={
                KnowledgeBaseChatConversation.CHAT_PROFILE_ID_CONFIG_KEY: profile.id
            },
            messages=[
                ChatUserMessageText(content="What does the report say?"),
                ChatMessageText(content="The report says X."),
            ],
        )

        conversation = self.factory.restore_conversation(row.id)

        # Restored onto the same row, so the next question continues it rather than starting another.
        self.assertEqual(conversation._conversation_id, row.id)
        self.assertEqual(conversation.knowledge_agent.chat_config.chat_profile_id, profile.id)
        self.assertEqual(len(conversation.chat_messages), 2)
        self.assertEqual(
            [message.message_type for message in conversation.get_visible_messages()],
            ["user-text", "text"],
        )

    def test_restore_conversation_round_trips_each_messages_focused_document_ids(self):
        """Document Focus (issue #31) rides each message, so restore must give each one back its own
        list rather than one shared focus for the whole conversation."""
        profile = self._create_profile()
        row = self._create_conversation_row(
            mode=ChatConversationMode.KNOWLEDGE_BASE.value,
            configuration={
                KnowledgeBaseChatConversation.CHAT_PROFILE_ID_CONFIG_KEY: profile.id
            },
            messages=[
                ChatUserMessageText(content="Q1", focused_document_ids=["doc-1"]),
                ChatMessageText(content="A1"),
                ChatUserMessageText(content="Q2", focused_document_ids=["doc-2", "doc-3"]),
                ChatMessageText(content="A2"),
                ChatUserMessageText(content="Q3"),
                ChatMessageText(content="A3"),
            ],
        )

        conversation = self.factory.restore_conversation(row.id)

        user_messages = [
            message
            for message in conversation.get_visible_messages()
            if message.message_type == "user-text"
        ]
        self.assertEqual(
            [message.focused_document_ids for message in user_messages],
            [["doc-1"], ["doc-2", "doc-3"], []],
        )

    def test_restore_conversation_replays_its_tool_turns_into_the_model_history(self):
        """The model is handed back what it already retrieved, not just what the reader saw."""
        profile = self._create_profile()
        row = self._create_conversation_row(
            mode=ChatConversationMode.KNOWLEDGE_BASE.value,
            configuration={
                KnowledgeBaseChatConversation.CHAT_PROFILE_ID_CONFIG_KEY: profile.id
            },
            messages=[
                ChatUserMessageText(content="What does the report say?"),
                ChatMessageToolCall(
                    tool_name="search_knowledge",
                    args={"query": "report"},
                    tool_call_id="call_1",
                ),
                ChatMessageToolResult(
                    tool_name="search_knowledge",
                    content="[1] report.md\nThe report says X.",
                    tool_call_id="call_1",
                ),
                ChatMessageText(content="The report says X."),
            ],
        )

        conversation = self.factory.restore_conversation(row.id)

        self.assertEqual(len(conversation.chat_messages), 4)
        self.assertEqual(len(conversation.get_visible_messages()), 2)
        self.assertEqual(len(conversation.knowledge_agent.get_message_history()), 4)

    def test_whether_a_conversation_can_be_reopened_is_answerable_without_credentials(self):
        """The check must not need a built factory, so a misconfigured lab still gets the reason.

        Building a factory resolves the chat API key. If the mode check came after that, a lab whose
        credentials are wrong would answer a retired conversation with a credentials error instead of
        saying the engine is retired — so this is a classmethod taking neither retriever nor key.
        """
        profile = self._create_profile()
        continuable = self._create_conversation_row(
            mode=ChatConversationMode.KNOWLEDGE_BASE.value,
            configuration={
                KnowledgeBaseChatConversation.CHAT_PROFILE_ID_CONFIG_KEY: profile.id
            },
        )
        legacy = self._create_conversation_row(
            mode=ChatConversationMode.RAG.value, configuration={}
        )

        self.assertEqual(
            KnowledgeBaseChatFactory.get_restorable_profile_id(continuable.id), profile.id
        )
        with self.assertRaises(KnowledgeBaseChatUnavailableError) as raised:
            KnowledgeBaseChatFactory.get_restorable_profile_id(legacy.id)
        self.assertEqual(str(raised.exception), LEGACY_CONVERSATION_MODE_MESSAGE)

    def test_restoring_a_legacy_rag_conversation_says_the_engine_is_retired(self):
        """Those rows point at datasets that no longer exist; the reason is what the user gets."""
        row = self._create_conversation_row(
            mode=ChatConversationMode.RAG.value,
            configuration={"rag_chat_id": "retired-dataset"},
            messages=[ChatUserMessageText(content="An old question")],
        )

        with self.assertRaises(KnowledgeBaseChatUnavailableError) as raised:
            self.factory.restore_conversation(row.id)

        self.assertEqual(str(raised.exception), LEGACY_CONVERSATION_MODE_MESSAGE)

    def test_restoring_another_modes_conversation_names_the_mode(self):
        row = self._create_conversation_row(
            mode=ChatConversationMode.AI_TABLE.value, configuration={}
        )

        with self.assertRaises(KnowledgeBaseChatUnavailableError) as raised:
            self.factory.restore_conversation(row.id)

        self.assertIn(ChatConversationMode.AI_TABLE.value, str(raised.exception))

    def test_restoring_a_legacy_ai_expert_conversation_says_the_engine_is_retired(self):
        """AI Expert is retired too (see ADR-0002): its rows report the same retirement message."""
        row = self._create_conversation_row(
            mode=ChatConversationMode.AI_EXPERT.value,
            configuration={"document_id": "doc-1"},
            messages=[ChatUserMessageText(content="An old question")],
        )

        with self.assertRaises(KnowledgeBaseChatUnavailableError) as raised:
            self.factory.restore_conversation(row.id)

        self.assertEqual(str(raised.exception), LEGACY_CONVERSATION_MODE_MESSAGE)

    def test_restoring_a_conversation_recording_no_profile_is_reported(self):
        row = self._create_conversation_row(
            mode=ChatConversationMode.KNOWLEDGE_BASE.value, configuration={}
        )

        with self.assertRaises(KnowledgeBaseChatUnavailableError):
            self.factory.restore_conversation(row.id)

    ############################################### ASSEMBLY ###############################################

    def test_an_assembled_chat_answers_persists_and_is_restorable(self):
        """The whole point of the factory, end to end: build, answer, reopen, continue.

        Everything the two halves have to agree on is exercised at once — the agent is wired to the
        retriever, the answer is attributed to what was retrieved, the row is written under the
        profile, and reopening that row replays enough history for the next question to land on the
        second scripted turn.

        The model is a scripted ``FunctionModel``, so no API call is made.
        """
        profile = self._create_profile()
        retriever = OneChunkRetriever()
        scripted_model = SingleAgentScriptedModel(
            turns=[
                ToolCall(SEARCH_KNOWLEDGE_TOOL_NAME, {"query": "budget"}),
                "The budget is 42000 euros.",
                "Yes, still 42000 euros.",
            ]
        )
        factory = KnowledgeBaseChatFactory(
            chat_app_name=CHAT_APP_NAME,
            retriever=retriever,
            model=scripted_model.build(),
        )

        conversation = factory.build_conversation(profile.id)
        conversation.create_conversation("What is the budget?")
        messages = list(
            conversation.call_conversation(ChatUserMessageText(content="What is the budget?"))
        )

        # It searched, and the answer carries what the search returned.
        self.assertEqual(retriever.calls, ["budget"])
        answer = messages[-1]
        self.assertIsInstance(answer, ChatMessageSource)
        self.assertEqual(answer.content, "The budget is 42000 euros.")
        self.assertEqual([source.document_name for source in answer.sources], ["budget.md"])

        # Reopened from its row, on the profile that row records.
        conversation_id = conversation._conversation_id
        restored = factory.restore_conversation(conversation_id)
        self.assertEqual(restored.knowledge_agent.get_chat_profile_id(), profile.id)
        self.assertEqual(
            [message.message_type for message in restored.get_visible_messages()],
            ["user-text", "source"],
        )

        # And it continues rather than starting over: landing on the third scripted turn is only
        # possible if the replayed history counted as the turns that already happened.
        continued = list(restored.call_conversation(ChatUserMessageText(content="Are you sure?")))
        self.assertEqual(continued[-1].content, "Yes, still 42000 euros.")

    def test_restoring_a_conversation_whose_profile_was_deleted_names_it(self):
        """``delete_profile`` leaves a dangling reference on purpose: the restore path reports it."""
        profile = self._create_profile()
        row = self._create_conversation_row(
            mode=ChatConversationMode.KNOWLEDGE_BASE.value,
            configuration={
                KnowledgeBaseChatConversation.CHAT_PROFILE_ID_CONFIG_KEY: profile.id
            },
        )
        self.profile_service.delete_profile(profile.id)

        with self.assertRaises(KnowledgeBaseChatUnavailableError) as raised:
            self.factory.restore_conversation(row.id)

        self.assertIn(profile.id, str(raised.exception))
