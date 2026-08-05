"""AI Expert: a question about one document, an answer from that document alone.

This is the ``AI_EXPERT`` mode of the existing, Reflex-free chat seam. Answering is the job of
:class:`~gws_ai_toolkit.models.chat.conversation.ai_expert_agent_ai.AiExpertAgentAi`, which this
conversation delegates to exactly as ``KnowledgeBaseChatConversation`` delegates to its own agent.
What is left here is what a *conversation* owns:

- **The transcript.** The streamed answer, and the error message a failed run becomes.
- **The restore.** The document id lands in the conversation's ``chat_configuration``, and the
  persisted rows are handed back to the agent as its message history.

No tool turn is ever recorded, because AI Expert exposes no tool: its document text is resolved
before the model is called. And no source is attached to an answer — the one document an AI Expert
conversation is about is named in its header, not in a source pill.

Two constraints shape the rest, both as in the knowledge-base chat:

- **Nothing live is held.** No engine, no LanceDB connection, no provider client — the conversation
  is pickled between Reflex events. See the agent's module docstring.
- **History is client-side.** No ``previous_response_id`` and no provider-side conversation handle:
  the persisted rows are the whole record, which is what makes a restore possible at all.
"""

from collections.abc import Generator

from gws_core import BaseModelDTO, Logger

from gws_ai_toolkit.core.agents.agent_events import (
    ErrorEvent,
    ResponseCompletedEvent,
    TextDeltaEvent,
    UserQueryTextEvent,
)
from gws_ai_toolkit.models.chat.conversation.ai_expert_agent_ai import AiExpertAgentAi
from gws_ai_toolkit.models.chat.message.chat_message_base import ChatMessageBase
from gws_ai_toolkit.models.chat.message.chat_message_error import ChatMessageError
from gws_ai_toolkit.models.chat.message.chat_message_types import ChatMessage
from gws_ai_toolkit.models.chat.message.chat_user_message import ChatUserMessageText

from .base_chat_conversation import (
    BaseChatConversation,
    BaseChatConversationConfig,
    ChatConversationMode,
)
from .chat_message_history_mapper import ChatMessageHistoryMapper

# Key an AI Expert conversation used before the embedded knowledge-base stack, naming the lab resource
# it was about. Nothing writes it any more; it is declared here, with the key that replaced it, because
# reading an old row is still part of this conversation's persisted contract (the admin history does).
LEGACY_RESOURCE_ID_CONFIG_KEY = "resource_id"


class AiExpertChatConversation(BaseChatConversation[ChatUserMessageText]):
    """A chat about one knowledge-base document, answering from that document only.

    Attributes:
        expert_agent: The agent answering the questions of this conversation.
    """

    # Key of the knowledge-base document id in ``chat_configuration``. Conversations persisted before
    # the move to the embedded knowledge-base stack carry a ``resource_id`` instead: they point at a
    # lab resource in a retired RAGFlow / Dify dataset, so they stay listable in history but cannot be
    # continued — a restore has no document to read.
    DOCUMENT_ID_CONFIG_KEY = "document_id"

    expert_agent: AiExpertAgentAi

    def __init__(
        self, config: BaseChatConversationConfig, expert_agent: AiExpertAgentAi
    ) -> None:
        """Build an AI Expert conversation.

        Args:
            config: Conversation-level configuration (chat app, user, persistence).
            expert_agent: The agent answering this conversation's questions, carrying the document,
                the AI Expert configuration, the retrieval seam and the provider key.
        """
        # The whole AI Expert configuration is persisted, not only the document id: it is what the
        # admin history shows of a conversation, and a configuration edited later must not change
        # what an old conversation reports it ran with.
        chat_configuration = expert_agent.chat_config.to_json_dict()
        chat_configuration[self.DOCUMENT_ID_CONFIG_KEY] = expert_agent.get_document_id()

        super().__init__(
            config,
            mode=ChatConversationMode.AI_EXPERT.value,
            chat_configuration=chat_configuration,
        )
        self.expert_agent = expert_agent

    ############################################### CHAT ###############################################

    def _call_ai_chat(
        self, user_message: ChatUserMessageText
    ) -> Generator[ChatMessage, None, None]:
        """Answer a question about the document, streaming the answer as it is produced.

        Args:
            user_message: The message from the user. Already persisted by the base class.

        Yields:
            ChatMessage: The user message, then the growing answer, then the finished answer — or a
                single error message if the run failed.
        """
        yield user_message

        user_query = UserQueryTextEvent(
            query=user_message.content, agent_id=self.expert_agent.id
        )

        try:
            for event in self.expert_agent.call_agent(user_query):
                yield from self._handle_agent_event(event)
        except Exception as exception:  # noqa: BLE001 - reported to the user as an error message
            # What lands here is resolving the document text: an unreachable vector store, or a
            # snapshot that cannot be read. Neither is something the model could correct, so the
            # agent lets it through and the turn ends on an error naming the cause.
            yield self._fail(exception)

    ############################################### EVENTS ###############################################

    def _handle_agent_event(self, event: BaseModelDTO) -> list[ChatMessage]:
        """Turn one agent event into the chat messages it produces.

        Args:
            event: The event emitted by the run.

        Returns:
            The messages to yield, which is empty for the events that only mark a boundary.
        """
        if isinstance(event, TextDeltaEvent):
            return [self.build_current_message(event.delta, external_id=event.response_id)]

        if isinstance(event, ResponseCompletedEvent):
            message = self.close_current_message(external_id=event.response_id)
            return [message] if message else []

        if isinstance(event, ErrorEvent):
            return [self._fail(event.message)]

        return []

    def _fail(self, error: Exception | str) -> ChatMessage:
        """Report a failed run as an error message, discarding whatever was half-streamed.

        The partial answer is dropped rather than closed: a truncated answer persisted as a complete
        one is worse than no answer, because nothing downstream can tell the two apart.

        Args:
            error: The exception raised by the run, or the message of a terminal error event.

        Returns:
            The persisted error message.
        """
        external_id = (
            self.current_response_message.external_id if self.current_response_message else None
        )
        self.current_response_message = None

        if isinstance(error, Exception):
            Logger.log_exception_stack_trace(error)

        return self.save_message(ChatMessageError(error=str(error), external_id=external_id))

    ############################################### RESTORE ###############################################

    def _restore_agent_history(self, messages: list[ChatMessageBase]) -> None:
        """Hand the agent back the history rebuilt from the persisted messages.

        Args:
            messages: The conversation's persisted messages, oldest first.
        """
        self.expert_agent.set_message_history(
            ChatMessageHistoryMapper.to_model_messages(messages)
        )
