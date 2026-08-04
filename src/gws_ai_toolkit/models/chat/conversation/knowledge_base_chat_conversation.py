"""The knowledge-base chat loop: a question against a chat profile, an answer with its sources.

This is the ``KNOWLEDGE_BASE`` mode of the existing, Reflex-free chat seam. It runs on pydantic-ai
through :class:`~gws_ai_toolkit.core.agents.agent_stream_adapter.AgentStreamAdapter`, the same
adapter the table agents run on — reused rather than re-derived, because the awkward parts (holding a
response's closing events back until its tools have run, turning the two pydantic-ai run failures
into one error event) are exactly the same problem here, and a second hand-written node walk would be
a second thing to keep correct.

What this class owns on top of the adapter:

- **The retrieval tool.** ``search_knowledge`` is scoped to the profile's bound knowledge bases and
  honours its ``top_k`` and ``score_threshold``. Every chunk it returns is collected, so the answer
  can be attributed to what was actually retrieved rather than to what the model chose to mention.
- **Sources.** The run's chunks are deduplicated and attached to the answer as ``RagChatSource``, the
  type the source pills and the chunk dialog already render.
- **Tool turns.** The call and its result are persisted as they happen, so a restored conversation
  replays what the model already retrieved instead of searching again.

Two constraints shape the rest:

- **Nothing live is held.** No engine, no LanceDB connection, no provider client — the conversation
  is pickled between Reflex events. It holds configuration, a retriever that builds engines per call,
  and the message history.
- **History is client-side.** No ``previous_response_id`` and no provider-side conversation handle:
  the persisted rows are the whole record, which is what makes a restore possible at all.
"""

from collections.abc import Callable, Generator
from dataclasses import dataclass, field
from typing import Any, Literal

from gws_core import BaseModelDTO, Logger
from pydantic_ai import Agent, RunContext
from pydantic_ai.messages import ModelMessage
from pydantic_ai.models import Model

from gws_ai_toolkit.core.agents.agent_stream_adapter import AgentStreamAdapter
from gws_ai_toolkit.core.agents.ai_model_factory import AiModelFactory
from gws_ai_toolkit.core.agents.base_function_agent_events import (
    ErrorEvent,
    FunctionCallEvent,
    FunctionSuccessEvent,
    ResponseCompletedEvent,
    TextDeltaEvent,
)
from gws_ai_toolkit.core.agents.sync_event_bridge import SyncEventBridge
from gws_ai_toolkit.core.agents.table.agent_event_list import AgentEventList
from gws_ai_toolkit.models.chat.conversation.knowledge_base_chat_config import (
    KnowledgeBaseChatConfig,
)
from gws_ai_toolkit.models.chat.message.chat_message_base import ChatMessageBase
from gws_ai_toolkit.models.chat.message.chat_message_error import ChatMessageError
from gws_ai_toolkit.models.chat.message.chat_message_tool_call import ChatMessageToolCall
from gws_ai_toolkit.models.chat.message.chat_message_types import ChatMessage
from gws_ai_toolkit.models.chat.message.chat_user_message import ChatUserMessageText
from gws_ai_toolkit.models.knowledge_base.knowledge_base_retriever import KnowledgeBaseRetriever
from gws_ai_toolkit.rag.common.rag_models import RagChatSource
from gws_ai_toolkit.rag.knowledge_base.knowledge_base_models import RetrievedChunk

from .base_chat_conversation import (
    BaseChatConversation,
    BaseChatConversationConfig,
    ChatConversationMode,
)
from .chat_message_history_mapper import ChatMessageHistoryMapper

# The tool name the model calls, and the name the default system prompt instructs it to call.
SEARCH_KNOWLEDGE_TOOL_NAME = "search_knowledge"

# What the tool reports when nothing matched. A miss is an answer, not a failure: telling the model
# to retry a failed tool would send it searching in a loop, whereas this lets it say it does not
# know — which is what the prompt asks of it.
NO_PASSAGE_FOUND_MESSAGE = (
    "No passage matched this query in the knowledge bases. "
    "Try different wording, or tell the user the documents do not cover it."
)


class KnowledgeSearchSuccessEvent(FunctionSuccessEvent):
    """What ``search_knowledge`` reported back to the model, in the adapter's event vocabulary.

    ``FunctionSuccessEvent`` carries no ``type`` of its own by design, so each tool family declares
    one. Emitting it is what gets the tool result *persisted in stream order* — between the call and
    the answer it led to — which is the order a restore replays.
    """

    type: Literal["knowledge_search_success"] = "knowledge_search_success"


@dataclass
class KnowledgeRetrievalDeps:
    """Dependencies handed to ``search_knowledge`` for one run.

    Attributes:
        adapter: The stream adapter, so the tool can emit its result into the running stream.
        agent_id: Id of the agent being run, stamped onto the emitted events.
        retriever: Where chunks come from. Injected, so the conversation can be driven with no
            database and no embedding provider.
        chat_config: The profile-derived configuration a search runs with.
        collected_chunks: Every chunk retrieved during this run, in retrieval order. Read once the
            answer is complete to build its sources.
    """

    adapter: AgentStreamAdapter
    agent_id: str
    retriever: KnowledgeBaseRetriever
    chat_config: KnowledgeBaseChatConfig
    collected_chunks: list[RetrievedChunk] = field(default_factory=list)


class KnowledgeBaseChatConversation(BaseChatConversation[ChatUserMessageText]):
    """A chat against a set of knowledge bases, answering from what it retrieves.

    Attributes:
        chat_config: The profile-derived configuration of this conversation.
        retriever: The retrieval seam; see :mod:`.knowledge_base_retriever`.
    """

    MAX_CONSECUTIVE_CALLS = 10
    MAX_CONSECUTIVE_ERRORS = 5

    CHAT_PROFILE_ID_CONFIG_KEY = "chat_profile_id"

    chat_config: KnowledgeBaseChatConfig
    retriever: KnowledgeBaseRetriever

    # Only the key is held, never a provider client: this object is pickled between Reflex events.
    _api_key: str | None
    _model: Model | None
    _message_history: list[ModelMessage]
    _tool_names_by_call_id: dict[str, str]

    def __init__(
        self,
        config: BaseChatConversationConfig,
        chat_config: KnowledgeBaseChatConfig,
        retriever: KnowledgeBaseRetriever,
        api_key: str | None = None,
        model: Model | None = None,
    ) -> None:
        """Build a knowledge-base conversation.

        Args:
            config: Conversation-level configuration (chat app, user, persistence).
            chat_config: The profile-derived configuration this chat runs with.
            retriever: Where ``search_knowledge`` retrieves from.
            api_key: API key for the configured provider, injected explicitly rather than left to
                the process environment — a Reflex app resolves it from credentials, and a lab that
                never exported ``OPENAI_API_KEY`` must still be able to chat.
            model: A pydantic-ai model overriding ``chat_config.model``. This is the seam tests use
                to substitute ``TestModel`` / ``FunctionModel`` and make no API call.
        """
        super().__init__(
            config,
            mode=ChatConversationMode.KNOWLEDGE_BASE.value,
            chat_configuration={self.CHAT_PROFILE_ID_CONFIG_KEY: chat_config.chat_profile_id},
        )
        self.chat_config = chat_config
        self.retriever = retriever
        self._api_key = api_key
        self._model = model
        self._message_history = []
        self._tool_names_by_call_id = {}

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

        collected_chunks: list[RetrievedChunk] = []

        try:
            events = SyncEventBridge.iterate(
                lambda emit: self._run(user_message, collected_chunks, emit)
            )
            for event in events:
                yield from self._handle_agent_event(event, collected_chunks)
        except Exception as exception:  # noqa: BLE001 - reported to the user as an error message
            yield self._fail(exception)

    async def _run(
        self,
        user_message: ChatUserMessageText,
        collected_chunks: list[RetrievedChunk],
        emit: Callable[[Any], None],
    ) -> None:
        """Drive one agent run, emitting its events.

        The history the run ends on is carried onto the conversation, so the next turn continues it.
        A run that failed returns the history it started from, which is what keeps a failed turn from
        poisoning the conversation.

        Args:
            user_message: The user's question.
            collected_chunks: List the tool appends every retrieved chunk to.
            emit: Callback pushing each event to the consumer.
        """
        agent_id = self._conversation_id or "knowledge-base-chat"
        adapter = AgentStreamAdapter(
            agent_id=agent_id, emit=emit, event_list=AgentEventList()
        )
        deps = KnowledgeRetrievalDeps(
            adapter=adapter,
            agent_id=agent_id,
            retriever=self.retriever,
            chat_config=self.chat_config,
            collected_chunks=collected_chunks,
        )

        self._message_history = await adapter.stream_run(
            agent=self._build_agent(),
            user_prompt=user_message.content,
            deps=deps,
            message_history=self._message_history or None,
            max_consecutive_calls=self.MAX_CONSECUTIVE_CALLS,
            max_consecutive_errors=self.MAX_CONSECUTIVE_ERRORS,
        )

    def _build_agent(self) -> Agent:
        """Build the pydantic-ai agent for a run.

        Built per run rather than held: an ``Agent`` carries the provider client, and this object is
        pickled between events. Overridable, together with the ``model`` constructor argument, so a
        test can drive the whole loop without an API call.

        Returns:
            The configured agent, with ``search_knowledge`` registered.
        """
        agent = Agent(
            model=AiModelFactory.build(self._model or self.chat_config.model, self._api_key),
            instructions=self.chat_config.system_prompt,
            deps_type=KnowledgeRetrievalDeps,
            retries={"tools": self.MAX_CONSECUTIVE_ERRORS},
        )

        @agent.tool(name=SEARCH_KNOWLEDGE_TOOL_NAME)
        async def search_knowledge(ctx: RunContext[KnowledgeRetrievalDeps], query: str) -> str:
            """Search the knowledge bases for passages relevant to a question.

            Args:
                query: What to search for. Prefer the wording of the documents over the wording of
                    the question, and search again with different terms if the passages returned
                    are not enough.
            """
            return self._search_knowledge(ctx, query)

        return agent

    def _search_knowledge(self, ctx: RunContext[KnowledgeRetrievalDeps], query: str) -> str:
        """Retrieve passages for a query, collect them, and report them back to the model.

        Args:
            ctx: The run context, carrying the dependencies of this run.
            query: What the model asked for.

        Returns:
            The formatted passages, or a message saying nothing matched.
        """
        deps = ctx.deps

        chunks = deps.retriever.retrieve(
            query=query,
            knowledge_base_ids=deps.chat_config.knowledge_base_ids,
            top_k=deps.chat_config.top_k,
            score_threshold=deps.chat_config.score_threshold,
        )
        deps.collected_chunks.extend(chunks)

        response = self._format_passages(chunks)

        deps.adapter.emit(
            KnowledgeSearchSuccessEvent(
                call_id=ctx.tool_call_id or "",
                response_id=deps.adapter.current_response_id,
                function_response=response,
                agent_id=deps.agent_id,
            )
        )

        return response

    @staticmethod
    def _format_passages(chunks: list[RetrievedChunk]) -> str:
        """Render retrieved chunks as the passages the model reads.

        Each passage is numbered and names its document: the numbering gives the model something to
        refer to in its answer, and the file name is what the reader recognises in the source pill.

        Args:
            chunks: The retrieved chunks, best first.

        Returns:
            The passages as one block of text.
        """
        if not chunks:
            return NO_PASSAGE_FOUND_MESSAGE

        passages = [
            f"[{index}] {chunk.filename}\n{chunk.content}"
            for index, chunk in enumerate(chunks, start=1)
        ]
        return "\n\n".join(passages)

    ############################################### EVENTS ###############################################

    def _handle_agent_event(
        self, event: BaseModelDTO, collected_chunks: list[RetrievedChunk]
    ) -> list[ChatMessage]:
        """Turn one agent event into the chat messages it produces.

        Args:
            event: The event emitted by the run.
            collected_chunks: Every chunk retrieved so far in this run.

        Returns:
            The messages to yield, which is empty for the events that only persist history.
        """
        if isinstance(event, TextDeltaEvent):
            return [self.build_current_message(event.delta, external_id=event.response_id)]

        if isinstance(event, FunctionCallEvent):
            # Recorded as it happens: the rebuilt history replays messages in the order they were
            # saved, and a search belongs before the answer it led to.
            self._tool_names_by_call_id[event.call_id] = event.function_name
            self.save_tool_call(
                tool_name=event.function_name,
                args=event.arguments,
                tool_call_id=event.call_id,
                external_id=event.response_id,
            )
            return []

        if isinstance(event, FunctionSuccessEvent):
            tool_name = self._tool_names_by_call_id.get(event.call_id)
            if tool_name:
                self.save_tool_result(
                    tool_name=tool_name,
                    content=event.function_response,
                    tool_call_id=event.call_id,
                    external_id=event.response_id,
                )
            return []

        if isinstance(event, ResponseCompletedEvent):
            # Only the response that actually streamed text has a message to close; the response
            # that merely called the tool closes to nothing, and its sources belong to the answer
            # that comes after it.
            if self.current_response_message is None:
                return []
            message = self.close_current_message(
                external_id=event.response_id, sources=self._build_sources(collected_chunks)
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
        self.current_response_message = None

        if isinstance(error, Exception):
            Logger.log_exception_stack_trace(error)

        return self.save_message(ChatMessageError(error=str(error)))

    @staticmethod
    def _build_sources(chunks: list[RetrievedChunk]) -> list[RagChatSource]:
        """Deduplicate the run's chunks and convert them to the persisted source type.

        A model that searches twice with different wording gets the same passage back twice, and a
        source pill shown twice is a bug the reader sees. Deduplication is by chunk id — the chunk is
        what a source points at — keeping the first occurrence, so the order stays the retrieval
        order.

        Args:
            chunks: Every chunk retrieved during the run, in retrieval order.

        Returns:
            The sources to attach to the answer.
        """
        seen_chunk_ids: set[str] = set()
        sources: list[RagChatSource] = []
        for chunk in chunks:
            if chunk.chunk_id in seen_chunk_ids:
                continue
            seen_chunk_ids.add(chunk.chunk_id)
            sources.append(chunk.to_rag_chat_source())
        return sources

    ############################################### RESTORE ###############################################

    def _restore_agent_history(self, messages: list[ChatMessageBase]) -> None:
        """Rebuild what the model already saw, tool turns included.

        Args:
            messages: The conversation's persisted messages, oldest first.
        """
        self._message_history = ChatMessageHistoryMapper.to_model_messages(messages)
        self._tool_names_by_call_id = {
            message.tool_call_id: message.tool_name
            for message in messages
            if isinstance(message, ChatMessageToolCall)
        }

    def get_message_history(self) -> list[ModelMessage]:
        """The client-side history the next turn continues from."""
        return self._message_history
