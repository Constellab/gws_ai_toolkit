"""AI Expert's Reflex state: one knowledge-base document, one conversation about it.

What this state resolves, and why each piece is resolved per call rather than held:

- **The document.** ``/ai-expert/[document_id]`` names a
  :class:`~gws_ai_toolkit.models.knowledge_base.knowledge_base_document.KnowledgeBaseDocument`, whose
  row id is also the ``document_id`` of its chunks. Only the handful of facts a conversation needs is
  kept, as an :class:`~gws_ai_toolkit.models.chat.conversation.ai_expert_document.AiExpertDocument` in
  a *backend* var — it carries a server-side snapshot path, which has no business reaching the
  browser.
- **The retriever**, not an engine: an engine holds a LanceDB connection and takes a file lock, and
  this state is pickled between events. ``EngineKnowledgeBaseRetriever`` builds one per retrieval.

Conversations persisted before the move to the embedded knowledge-base stack carry a ``resource_id``
rather than a ``document_id``: they point at a lab resource in a retired RAGFlow / Dify dataset, so
they stay listable in history but cannot be continued, and a restore sends the user back to the
document browser instead of failing opaquely.
"""

import reflex as rx
from gws_ai_toolkit.models.chat.chat_conversation import ChatConversation
from gws_ai_toolkit.models.chat.chat_conversation_service import ChatConversationService
from gws_ai_toolkit.models.chat.conversation.ai_expert_agent_ai import AiExpertAgentAi
from gws_ai_toolkit.models.chat.conversation.ai_expert_chat_config import AiExpertChatConfig
from gws_ai_toolkit.models.chat.conversation.ai_expert_chat_conversation import (
    AiExpertChatConversation,
)
from gws_ai_toolkit.models.chat.conversation.ai_expert_document import AiExpertDocument
from gws_ai_toolkit.models.chat.conversation.base_chat_conversation import (
    BaseChatConversation,
    BaseChatConversationConfig,
)
from gws_ai_toolkit.models.knowledge_base.knowledge_base_service import KnowledgeBaseService
from gws_core import Logger
from gws_reflex_main import ReflexMainState

from ..chat_base.conversation_chat_state_base import ConversationChatStateBase
from ..core.app_config_state import AppConfigState
from ..history.history_state import HistoryState
from ..knowledge_base.core.document_open_action import build_open_document_event_for_id
from ..knowledge_base.core.knowledge_base_app_state import KnowledgeBaseAppState
from .ai_expert_config_state import AiExpertConfigState


class AiExpertState(ConversationChatStateBase, rx.State):
    """State management for AI Expert - specialized document-focused chat functionality.

    Key Features:
        - Chat about one indexed knowledge-base document
        - Two processing modes (relevant_chunks, full_text_chunk)
        - Streaming answers on pydantic-ai
        - Automatic conversation persistence

    Processing Modes:
        - relevant_chunks: retrieves the passages of that document matching the question
        - full_text_chunk: reads the document's snapshot, whole and exact
    """

    # UI configuration
    subtitle: str | None = None

    # Backend var: it carries the snapshot path, so it must never be serialised to the frontend.
    _document: AiExpertDocument | None = None

    ############################################### CONVERSATION ###############################################

    async def _create_conversation(self) -> BaseChatConversation:
        """Create a new AiExpertChatConversation for the loaded document.

        Returns:
            BaseChatConversation: A new AiExpertChatConversation whose agent is configured with the
                document, the AI Expert configuration and a connection-free retriever.

        Raises:
            ValueError: If no document is loaded, or if the embedding configuration cannot be
                resolved (missing or malformed credentials).
        """
        if not self._document:
            raise ValueError("No document loaded for this AI Expert conversation")

        app_config_state = await AppConfigState.get_instance(self)
        chat_app_name = await app_config_state.get_chat_app_name()

        expert_config_state = await self.get_state(AiExpertConfigState)
        config: AiExpertChatConfig = await expert_config_state.get_config()

        main_state = await self.get_state(ReflexMainState)
        user = await main_state.get_current_user()

        # The retriever and the key are resolved per conversation, never held: a retriever must build
        # its engine per call (a LanceDB connection and a file lock cannot survive a pickled state),
        # and an API key is a secret that has no business on a serialised state. Both come from the
        # knowledge-base app state, so AI Expert and the knowledge-base chat read one configuration.
        knowledge_base_state = await self.get_state(KnowledgeBaseAppState)

        expert_agent = AiExpertAgentAi(
            chat_config=config,
            document=self._document,
            retriever=await knowledge_base_state.build_retriever(main_state),
            api_key=await knowledge_base_state.get_chat_api_key(main_state),
        )

        conv_config = BaseChatConversationConfig(
            chat_app_name, store_conversation_in_db=True, user=user.to_dto() if user else None
        )

        return AiExpertChatConversation(config=conv_config, expert_agent=expert_agent)

    async def _restore_conversation(self, conversation_id: str) -> None:
        """Restore an AiExpertChatConversation for an existing conversation.

        The document has already been loaded from the conversation's configuration by
        :meth:`load_conversation_from_url`, so this only rebuilds the conversation object and hands
        it back its persisted messages.
        """
        conversation = await self._create_conversation()

        main_state = await self.get_state(ReflexMainState)
        with await main_state.authenticate_user():
            db_conversation: ChatConversation = ChatConversation.get_by_id_and_check(
                conversation_id
            )
            conversation._conversation_id = conversation_id
            conversation._external_conversation_id = db_conversation.external_conversation_id

            conversation_service = ChatConversationService()
            conversation.restore_messages(
                conversation_service.get_messages_of_conversation(conversation_id)
            )

        self._conversation = conversation

    async def _after_conversation_updated(self) -> rx.event.EventSpec | None:
        """Refresh sidebar conversations and update URL after a message is sent."""
        async with self:
            history_state = await self.get_state(HistoryState)
            await history_state.load_conversations()

        if self._conversation and self._conversation._conversation_id:
            conversation_id = self._conversation._conversation_id
            return rx.call_script(
                f'window.history.replaceState({{}}, "", "/ai-expert/chat/{conversation_id}")'
            )
        return None

    ############################################### LOADING ###############################################

    async def _load_document(self, document_id: str) -> bool:
        """Load a knowledge-base document and update the UI state.

        Args:
            document_id: Id of the document to chat about.

        Returns:
            True if the document exists and was loaded, False otherwise.
        """
        main_state = await self.get_state(ReflexMainState)
        with await main_state.authenticate_user():
            document = KnowledgeBaseService().get_document(document_id)

        if document is None:
            Logger.warning(f"AI Expert: knowledge base document '{document_id}' does not exist")
            return False

        # Switching document mid-page must not carry the previous document's exchange over.
        if self._document and self._document.document_id != document.id:
            self.clear_chat()

        self._document = AiExpertDocument.from_document(document)
        self.subtitle = document.filename

        expert_config_state = await self.get_state(AiExpertConfigState)
        config: AiExpertChatConfig = await expert_config_state.get_config()
        self.placeholder_text = config.placeholder_text

        return True

    async def load_document_from_url(self) -> rx.event.EventSpec | None:
        """Handle page load for /ai-expert/[document_id].

        Always starts a fresh conversation for the given document.
        """
        document_id = self.document_id if hasattr(self, "document_id") else None

        if not document_id:
            return None

        # Always start a new conversation when navigating to this page.
        self.clear_chat()

        if not await self._load_document(document_id):
            self._document = None
            self.subtitle = None
            return rx.redirect("/ai-expert")

        return None

    @rx.event
    async def load_conversation_from_url(self) -> rx.event.EventSpec | None:
        """Handle page load for /ai-expert/chat/[conversation_id].

        Loads the conversation and the document it is about from the database.
        """
        conversation_id = self.conversation_id if hasattr(self, "conversation_id") else None

        if not conversation_id:
            return None

        if self._conversation and self._conversation._conversation_id == conversation_id:
            return None

        try:
            main_state = await self.get_state(ReflexMainState)
            with await main_state.authenticate_user():
                db_conversation: ChatConversation = ChatConversation.get_by_id_and_check(
                    conversation_id
                )
                document_id = db_conversation.configuration.get(
                    AiExpertChatConversation.DOCUMENT_ID_CONFIG_KEY
                )

            # No document id at all is a conversation from the retired RAG stack; an id that no
            # longer resolves is a document that has since been deleted. Neither can be continued.
            if not document_id or not await self._load_document(document_id):
                self.clear_chat()
                return rx.redirect("/ai-expert")

            await self.load_conversation(conversation_id)
        except Exception as exception:  # noqa: BLE001 - a broken restore sends the user back
            Logger.log_exception_stack_trace(exception)
            self.clear_chat()
            return rx.redirect("/ai-expert")

        return None

    ############################################### ACTIONS ###############################################

    @rx.event
    async def open_current_document(self) -> rx.event.EventSpec | None:
        """Open the document the conversation is about, however its source offers it."""
        if not self._document:
            return None

        main_state = await self.get_state(ReflexMainState)
        with await main_state.authenticate_user():
            return build_open_document_event_for_id(self._document.document_id)

    def get_current_document(self) -> AiExpertDocument | None:
        """The document this conversation is about, for the states and components around the chat."""
        return self._document
