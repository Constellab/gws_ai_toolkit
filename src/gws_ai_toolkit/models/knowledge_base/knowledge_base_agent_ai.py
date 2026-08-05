"""The agent behind a knowledge-base chat: answer a question from what it retrieves.

This is a :class:`~gws_ai_toolkit.core.agents.base_pydantic_agent_ai.BasePydanticAgentAi` like the
table agents, so the run loop, the client-side history, the tool dispatch and the error handling are
the brick's single implementation rather than a second one written for this chat. What this agent
adds is what is specific to answering from documents:

- **The retrieval tool.** ``search_knowledge`` is scoped to the profile's bound knowledge bases and
  honours its ``top_k`` and ``score_threshold``. Every chunk it returns is collected, so the answer
  can be attributed to what was actually retrieved rather than to what the model chose to mention.
- **Sources.** The chunks of a run are deduplicated into ``RagChatSource``, the type the source
  pills and the chunk dialog already render.

**Nothing live is held.** No engine, no LanceDB connection, no provider client: the conversation
holding this agent is pickled between Reflex events. Retrieval goes through
:class:`~gws_ai_toolkit.models.knowledge_base.knowledge_base_retriever.KnowledgeBaseRetriever`,
which builds its engine per call, and the provider key is held as a string.
"""

from collections.abc import AsyncGenerator, Callable

from gws_core import BaseModelDTO
from pydantic import Field
from pydantic_ai.models import Model

from gws_ai_toolkit.core.agents.agent_events import (
    FunctionCallEvent,
    FunctionErrorEvent,
    UserQueryTextEvent,
)
from gws_ai_toolkit.core.agents.base_pydantic_agent_ai import AgentToolSpec, BasePydanticAgentAi
from gws_ai_toolkit.rag.common.rag_models import RagChatSource
from gws_ai_toolkit.rag.knowledge_base.knowledge_base_models import RetrievedChunk

from .knowledge_base_agent_ai_events import KnowledgeBaseAgentEvent, KnowledgeSearchSuccessEvent
from .knowledge_base_chat_config import KnowledgeBaseChatConfig
from .knowledge_base_retriever import KnowledgeBaseRetriever

# The tool name the model calls, and the name the default system prompt instructs it to call.
SEARCH_KNOWLEDGE_TOOL_NAME = "search_knowledge"

# What the tool reports when nothing matched. A miss is an answer, not a failure: telling the model
# to retry a failed tool would send it searching in a loop, whereas this lets it say it does not
# know — which is what the prompt asks of it.
NO_PASSAGE_FOUND_MESSAGE = (
    "No passage matched this query in the knowledge bases. "
    "Try different wording, or tell the user the documents do not cover it."
)

# Answering from retrieved passages is not a creative task: a low temperature keeps the answer close
# to what the documents say. A profile configures the model but not this, so it stays a constant
# rather than becoming a setting nothing sets.
DEFAULT_TEMPERATURE = 0.3


class KnowledgeSearchConfig(BaseModelDTO):
    """Arguments of the ``search_knowledge`` tool, as the model sees them."""

    query: str = Field(
        description=(
            "What to search for in the knowledge bases. Prefer the wording of the documents over "
            "the wording of the question, and search again with different terms if the passages "
            "returned are not enough."
        ),
    )

    class Config:
        extra = "forbid"  # Prevent additional properties


class KnowledgeBaseAgentAi(BasePydanticAgentAi[KnowledgeBaseAgentEvent, UserQueryTextEvent]):
    """Answers a question from the passages it retrieves out of a profile's knowledge bases.

    Attributes:
        chat_config: The profile-derived configuration a run searches and answers with.
        retriever: Where ``search_knowledge`` retrieves from. Injected, so the agent can be driven
            with no database and no embedding provider.
    """

    chat_config: KnowledgeBaseChatConfig
    retriever: KnowledgeBaseRetriever

    # Every chunk retrieved during the current run, in retrieval order.
    _retrieved_chunks: list[RetrievedChunk]

    def __init__(
        self,
        chat_config: KnowledgeBaseChatConfig,
        retriever: KnowledgeBaseRetriever,
        api_key: str | None = None,
        model: Model | None = None,
        temperature: float = DEFAULT_TEMPERATURE,
    ) -> None:
        """Build a knowledge-base agent.

        Args:
            chat_config: The configuration of the chat this agent answers for.
            retriever: Where ``search_knowledge`` retrieves from.
            api_key: API key for the configured provider, injected explicitly rather than left to
                the process environment — a Reflex app resolves it from credentials, and a lab that
                never exported ``OPENAI_API_KEY`` must still be able to chat.
            model: A pydantic-ai model overriding ``chat_config.model``. This is the seam tests use
                to substitute ``TestModel`` / ``FunctionModel`` and make no API call.
            temperature: Sampling temperature; see :data:`DEFAULT_TEMPERATURE`.
        """
        super().__init__(
            openai_api_key=api_key,
            model=model or chat_config.model,
            temperature=temperature,
        )
        self.chat_config = chat_config
        self.retriever = retriever
        self._retrieved_chunks = []

    # ------------------------------------------------------------------ public surface

    def get_chat_profile_id(self) -> str:
        """Id of the profile this agent answers for, which is what a restore restores from."""
        return self.chat_config.chat_profile_id

    def get_retrieved_sources(self) -> list[RagChatSource]:
        """Deduplicate what the current run retrieved and convert it to the persisted source type.

        A model that searches twice with different wording gets the same passage back twice, and a
        source pill shown twice is a bug the reader sees. Deduplication is by chunk id — the chunk
        is what a source points at — keeping the first occurrence, so the order stays the retrieval
        order.

        Returns:
            The sources to attach to the answer.
        """
        seen_chunk_ids: set[str] = set()
        sources: list[RagChatSource] = []
        for chunk in self._retrieved_chunks:
            if chunk.chunk_id in seen_chunk_ids:
                continue
            seen_chunk_ids.add(chunk.chunk_id)
            sources.append(chunk.to_rag_chat_source())
        return sources

    # ------------------------------------------------------------------ agent definition

    def _get_ai_instruction(self, user_query: UserQueryTextEvent) -> str:
        """The profile's system prompt, which is where the obligation to search is stated.

        Args:
            user_query: The user's question, which the instructions do not depend on here.

        Returns:
            The instructions handed to the model for this run.
        """
        return self.chat_config.system_prompt

    def _get_tools(self) -> list[AgentToolSpec]:
        """Declare the retrieval tool exposed to the model.

        Returns:
            The single tool specification of this agent.
        """
        return [
            AgentToolSpec(
                name=SEARCH_KNOWLEDGE_TOOL_NAME,
                description=(
                    "Search the knowledge bases for passages relevant to a question. Call this "
                    "before answering, and answer from the passages it returns."
                ),
                parameters=KnowledgeSearchConfig.model_json_schema(),
            )
        ]

    async def _run(
        self, user_query: UserQueryTextEvent, emit: Callable[[KnowledgeBaseAgentEvent], None]
    ) -> None:
        """Drive one run, starting from an empty set of retrieved chunks.

        The reset is here rather than in a caller because the sources of an answer are what *that*
        answer's run retrieved: carrying the previous turn's chunks over would attribute a new
        answer to passages it never saw.

        Args:
            user_query: The user's question.
            emit: Callback pushing each event to the consumer.
        """
        self._retrieved_chunks = []
        await super()._run(user_query, emit)

    async def _handle_function_call(
        self, function_call_event: FunctionCallEvent, user_query: UserQueryTextEvent
    ) -> AsyncGenerator[KnowledgeBaseAgentEvent, None]:
        """Retrieve passages for the model's query, collect them, and report them back.

        A retrieval that raises is deliberately *not* turned into a ``FunctionErrorEvent``: a
        broken index or an unreachable database is not something the model can correct by
        rephrasing, so the exception propagates and the run ends on an error naming the cause,
        instead of five retries ending on "maximum consecutive errors reached".

        Args:
            function_call_event: The tool call the model made.
            user_query: The user's question. Its query text is not what retrieval searches with —
                the model's own query is — but its ``focused_document_ids`` is what scopes the
                search: Document Focus (issue #29) is enforced here, not offered to the model as a
                choice, so a message with focus set narrows every search of its turn to those
                documents and a message without it searches unscoped.

        Yields:
            The event reporting the passages back to the model, or a tool error the model is asked
            to correct.
        """
        query = str(function_call_event.arguments.get("query") or "").strip()

        if not query:
            yield FunctionErrorEvent(
                message="No query provided. Call the tool again with what to search for.",
                call_id=function_call_event.call_id,
                response_id=function_call_event.response_id,
                agent_id=self.id,
            )
            return

        chunks = self.retriever.retrieve(
            query=query,
            knowledge_base_ids=self.chat_config.knowledge_base_ids,
            top_k=self.chat_config.top_k,
            score_threshold=self.chat_config.score_threshold,
            document_ids=user_query.focused_document_ids or None,
        )
        self._retrieved_chunks.extend(chunks)

        yield KnowledgeSearchSuccessEvent(
            call_id=function_call_event.call_id,
            response_id=function_call_event.response_id,
            function_response=self._format_passages(chunks),
            agent_id=self.id,
        )

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
