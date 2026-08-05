"""Building a knowledge-base chat, and refusing the ones that cannot be built.

Two operations, and every entry point needs both: start a chat from a profile, or reopen one from a
conversation row. They live here rather than in the Reflex state because the HTTP route of
``knowledge_base_public_api_plan.md`` needs exactly the same two, and a chat loop assembled twice
would drift.

**A restore fails in four legitimate ways**, and each one is a sentence a user can act on rather
than a stack trace:

- the row is a legacy ``rag`` conversation, whose datasets are retired;
- the row belongs to another mode, so the URL is pointing at the wrong page;
- the row records no ``chat_profile_id``, so there is nothing to restore *from*;
- the row's profile has since been deleted — a dangling reference
  :meth:`~.rag_chat_profile_service.RagChatProfileService.delete_profile` creates deliberately.

All four raise :class:`KnowledgeBaseChatUnavailableError`, so a caller has one thing to catch and one
message to show.

**Nothing live is held.** The factory holds a retriever (configuration, not a connection) and an API
key string; the conversation it returns is pickled between Reflex events. See
:mod:`~.knowledge_base_agent_ai`.
"""

from gws_core import UserDTO
from pydantic_ai.models import Model

from gws_ai_toolkit.models.chat.chat_conversation import ChatConversation
from gws_ai_toolkit.models.chat.chat_conversation_service import ChatConversationService
from gws_ai_toolkit.models.chat.conversation.base_chat_conversation import (
    LEGACY_CONVERSATION_MODE_MESSAGE,
    BaseChatConversationConfig,
    ChatConversationMode,
)
from gws_ai_toolkit.models.chat.conversation.knowledge_base_chat_conversation import (
    KnowledgeBaseChatConversation,
)
from gws_ai_toolkit.models.knowledge_base.knowledge_base_agent_ai import KnowledgeBaseAgentAi
from gws_ai_toolkit.models.knowledge_base.knowledge_base_chat_config import KnowledgeBaseChatConfig
from gws_ai_toolkit.models.knowledge_base.knowledge_base_retriever import KnowledgeBaseRetriever
from gws_ai_toolkit.models.knowledge_base.rag_chat_profile_service import RagChatProfileService


class KnowledgeBaseChatUnavailableError(Exception):
    """A chat that cannot be started or continued, carrying the reason to show the user."""


class KnowledgeBaseChatFactory:
    """Assembles a knowledge-base chat: profile in, conversation out."""

    _chat_app_name: str
    _retriever: KnowledgeBaseRetriever
    _api_key: str | None
    _user: UserDTO | None
    _model: Model | None

    def __init__(
        self,
        chat_app_name: str,
        retriever: KnowledgeBaseRetriever,
        api_key: str | None = None,
        user: UserDTO | None = None,
        model: Model | None = None,
    ) -> None:
        """
        :param chat_app_name: the chat app conversations of this chat belong to
        :param retriever: where ``search_knowledge`` retrieves from; holds configuration only, and
                          builds its engine per call — never a live connection (see the module
                          docstring)
        :param api_key: API key for the chat model's provider, injected explicitly rather than left
                        to the process environment
        :param user: the user the conversation rows are stamped with
        :param model: a pydantic-ai model overriding the profile's own, which is the seam tests use
                      to substitute ``TestModel`` / ``FunctionModel``
        """
        self._chat_app_name = chat_app_name
        self._retriever = retriever
        self._api_key = api_key
        self._user = user
        self._model = model

    ############################################### BUILD ###############################################

    def build_conversation(self, chat_profile_id: str) -> KnowledgeBaseChatConversation:
        """A new chat against a profile.

        No row is written here: a conversation row appears when the first question is asked, so
        opening a chat page and leaving leaves nothing behind.

        :param chat_profile_id: the profile the chat runs with
        :raises KnowledgeBaseChatUnavailableError: if no profile is named, or none exists with that id
        """
        chat_config = self._get_chat_config(chat_profile_id)

        agent = KnowledgeBaseAgentAi(
            chat_config=chat_config,
            retriever=self._retriever,
            api_key=self._api_key,
            model=self._model,
        )

        return KnowledgeBaseChatConversation(
            config=BaseChatConversationConfig(
                self._chat_app_name, store_conversation_in_db=True, user=self._user
            ),
            knowledge_agent=agent,
        )

    ############################################### RESTORE ###############################################

    @classmethod
    def get_restorable_profile_id(cls, conversation_id: str) -> str:
        """The profile a persisted conversation can be reopened on.

        A classmethod, and free of every dependency a built factory carries — no retriever, no API
        key — because a caller has to be able to ask *"can this be continued?"* before resolving
        chat credentials. A lab whose credentials are misconfigured must still be told that a retired
        conversation is retired, rather than being handed a credentials error about a conversation
        that was never going to open.

        :param conversation_id: the conversation being examined
        :raises NotFoundException: if the conversation does not exist
        :raises KnowledgeBaseChatUnavailableError: if it cannot be continued — see the module
                docstring for the four ways that happens
        """
        return cls.get_restorable_profile_id_from_row(
            ChatConversation.get_by_id_and_check(conversation_id)
        )

    def restore_conversation(self, conversation_id: str) -> KnowledgeBaseChatConversation:
        """Reopen a persisted conversation, ready to continue.

        The profile comes from the row's own configuration rather than from whatever the UI happens
        to have selected: a conversation is a conversation *with a profile*, and continuing it under
        another one would silently change the answers halfway through.

        :param conversation_id: the conversation to reopen
        :raises NotFoundException: if the conversation does not exist
        :raises KnowledgeBaseChatUnavailableError: if it cannot be continued — see the module
                docstring for the four ways that happens
        """
        row = ChatConversation.get_by_id_and_check(conversation_id)
        chat_profile_id = self.get_restorable_profile_id_from_row(row)

        conversation = self.build_conversation(chat_profile_id)
        conversation._conversation_id = conversation_id
        conversation._external_conversation_id = row.external_conversation_id
        conversation.restore_messages(
            ChatConversationService().get_messages_of_conversation(conversation_id)
        )
        return conversation

    @staticmethod
    def get_restorable_profile_id_from_row(row: ChatConversation) -> str:
        """The profile a persisted conversation is to be reopened on, from its already-fetched row.

        The row-taking half of :meth:`get_restorable_profile_id`, for a caller that already fetched
        the row for another reason (checking `ChatConversationMode.is_legacy` generically, say) and
        would otherwise fetch it a second time.

        :param row: the conversation's row
        :raises KnowledgeBaseChatUnavailableError: if the row is of another mode, or records no
                profile
        """
        if row.mode != ChatConversationMode.KNOWLEDGE_BASE.value:
            # A legacy row is the case worth naming: those conversations were run against RAGFlow or
            # Dify datasets that no longer exist, so they stay readable and stop there.
            if ChatConversationMode(row.mode).is_legacy:
                raise KnowledgeBaseChatUnavailableError(LEGACY_CONVERSATION_MODE_MESSAGE)
            raise KnowledgeBaseChatUnavailableError(
                f"This is a '{row.mode}' conversation, which cannot be continued as a "
                "knowledge-base chat."
            )

        chat_profile_id = (row.configuration or {}).get(
            KnowledgeBaseChatConversation.CHAT_PROFILE_ID_CONFIG_KEY
        )
        if not chat_profile_id:
            raise KnowledgeBaseChatUnavailableError(
                "This conversation records no chat profile, so it cannot be continued."
            )
        return str(chat_profile_id)

    ############################################### INTERNALS ###############################################

    def _get_chat_config(self, chat_profile_id: str) -> KnowledgeBaseChatConfig:
        """The configuration a run against this profile searches and answers with.

        :raises KnowledgeBaseChatUnavailableError: if no profile is named, or none exists with that id
        """
        if not chat_profile_id:
            raise KnowledgeBaseChatUnavailableError(
                "No chat profile selected. Pick one before asking a question."
            )

        profile = RagChatProfileService().get_profile(chat_profile_id)
        if profile is None:
            raise KnowledgeBaseChatUnavailableError(
                f"The chat profile '{chat_profile_id}' no longer exists."
            )

        return KnowledgeBaseChatConfig.from_profile(profile)
