"""The knowledge-base chat: a question against a chat profile, an answer with its sources.

This is the ``KNOWLEDGE_BASE`` mode of the existing, Reflex-free chat seam. Answering is the job of
:class:`~gws_ai_toolkit.models.knowledge_base.knowledge_base_agent_ai.KnowledgeBaseAgentAi`, which
this conversation delegates to exactly as ``AiTableAgentChatConversation`` delegates to its table
agent. What is left here is what a *conversation* owns:

- **The transcript.** The streamed answer, the sources attached to it, the tool turns kept so a
  restored conversation replays what the model already retrieved, and the error message a failed run
  becomes.
- **The restore.** The profile id lands in the conversation's ``chat_configuration``, and the
  persisted rows are handed back to the agent as its message history.

Two constraints shape the rest:

- **Nothing live is held.** No engine, no LanceDB connection, no provider client — the conversation
  is pickled between Reflex events. See the agent's module docstring.
- **History is client-side.** No ``previous_response_id`` and no provider-side conversation handle:
  the persisted rows are the whole record, which is what makes a restore possible at all.
"""

from collections.abc import Generator

from gws_core import BaseModelDTO, Logger

from gws_ai_toolkit.core.agents.agent_events import (
    ErrorEvent,
    FunctionCallEvent,
    ResponseCompletedEvent,
    TextDeltaEvent,
    UserQueryTextEvent,
)
from gws_ai_toolkit.models.chat.message.chat_message_base import ChatMessageBase
from gws_ai_toolkit.models.chat.message.chat_message_error import ChatMessageError
from gws_ai_toolkit.models.chat.message.chat_message_types import ChatMessage
from gws_ai_toolkit.models.chat.message.chat_user_message import ChatUserMessageText
from gws_ai_toolkit.models.knowledge_base.knowledge_base_agent_ai import KnowledgeBaseAgentAi

from .base_chat_conversation import (
    BaseChatConversation,
    BaseChatConversationConfig,
    ChatConversationMode,
)
from .chat_message_history_mapper import ChatMessageHistoryMapper


class KnowledgeBaseChatConversation(BaseChatConversation[ChatUserMessageText]):
    """A chat against a set of knowledge bases, answering from what it retrieves.

    Attributes:
        knowledge_agent: The agent answering the questions of this conversation.
    """

    CHAT_PROFILE_ID_CONFIG_KEY = "chat_profile_id"

    knowledge_agent: KnowledgeBaseAgentAi

    def __init__(
        self, config: BaseChatConversationConfig, knowledge_agent: KnowledgeBaseAgentAi
    ) -> None:
        """Build a knowledge-base conversation.

        Args:
            config: Conversation-level configuration (chat app, user, persistence).
            knowledge_agent: The agent answering this conversation's questions, carrying the
                profile configuration, the retrieval seam and the provider key.
        """
        super().__init__(
            config,
            mode=ChatConversationMode.KNOWLEDGE_BASE.value,
            chat_configuration={
                self.CHAT_PROFILE_ID_CONFIG_KEY: knowledge_agent.get_chat_profile_id()
            },
        )
        self.knowledge_agent = knowledge_agent

    ############################################### CHAT ###############################################

    def _call_ai_chat(
        self, user_message: ChatUserMessageText
    ) -> Generator[ChatMessage, None, None]:
        """Answer a question, streaming the answer and closing it with its sources.

        Args:
            user_message: The message from the user. Already persisted by the base class.

        Yields:
            ChatMessage: The user message, then the growing answer, then the answer with its
                sources — or a single error message if the run failed.
        """
        yield user_message

        user_query = UserQueryTextEvent(
            query=user_message.content, agent_id=self.knowledge_agent.id
        )

        try:
            for event in self.knowledge_agent.call_agent(user_query):
                yield from self._handle_agent_event(event)
        except Exception as exception:  # noqa: BLE001 - reported to the user as an error message
            # What lands here is a retrieval that raised: an unreachable database or a broken index
            # is not something the model could correct by rephrasing, so the agent lets it through
            # and the turn ends on an error naming the cause.
            yield self._fail(exception)

    ############################################### EVENTS ###############################################

    def _handle_agent_event(self, event: BaseModelDTO) -> list[ChatMessage]:
        """Turn one agent event into the chat messages it produces.

        Args:
            event: The event emitted by the run.

        Returns:
            The messages to yield, which is empty for the events that only persist history.
        """
        if isinstance(event, FunctionCallEvent):
            # Two things happen here and their order is the point. The model stopped talking and
            # started searching, so what it said is a complete message: it is closed first, then
            # the call is recorded, which is the order the exchange happened in and therefore the
            # order a restore replays. Waiting for the response's own completion event instead
            # would file the sentence *after* the search it came before, since the adapter holds a
            # response's closing events back until its tools have run.
            closed_message = self.close_current_message(external_id=event.response_id)
            self.record_tool_turn(event)
            return [closed_message] if closed_message else []

        # Tool results are recorded as they happen. Every other event carries no tool turn.
        self.record_tool_turn(event)

        if isinstance(event, TextDeltaEvent):
            return [self.build_current_message(event.delta, external_id=event.response_id)]

        if isinstance(event, ResponseCompletedEvent):
            # Only the response that answered still has a message to close: a response that
            # searched was closed when its search started, and the one that only searched had
            # nothing to close in the first place.
            message = self.close_current_message(
                external_id=event.response_id,
                sources=self.knowledge_agent.get_retrieved_sources(),
            )
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
        """Hand the agent back the history rebuilt from the persisted messages, tool turns included.

        Args:
            messages: The conversation's persisted messages, oldest first.
        """
        self.knowledge_agent.set_message_history(
            ChatMessageHistoryMapper.to_model_messages(messages)
        )
