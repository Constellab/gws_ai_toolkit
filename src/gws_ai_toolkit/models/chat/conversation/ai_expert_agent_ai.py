"""The agent behind AI Expert: one document substituted into the instructions, then an answer.

AI Expert is **not a tool-calling agent**. It exposes no tool at all: the document text is resolved
before the model is called and substituted into the instructions, so a run is one model request and
its stream. What differs between its two modes is only where that text comes from:

===================  ==========================================================================
``relevant_chunks``  ``retriever.retrieve(..., document_ids=[document_id])`` — the passages of
                     *this* document that match the question, and nothing from any other document
``full_text_chunk``  the document's **snapshot**, read directly: the exact text, with no
                     chunk-boundary artefacts and no engine call at all
===================  ==========================================================================

It is a :class:`~gws_ai_toolkit.core.agents.base_pydantic_agent_ai.BasePydanticAgentAi` like every
other agent in this brick, so the run loop, the streaming, the client-side history and the error
handling are the brick's single implementation rather than a second one written for this chat. The
subclass is little more than :meth:`AiExpertAgentAi._get_ai_instruction` — which is exactly the shape
the migration plan predicted once ``full_file`` was removed.

Because instructions are rebuilt per run (and pydantic-ai keeps them out of the message history),
``relevant_chunks`` retrieves for **each question** rather than once per conversation, and a follow-up
question is answered from the passages that match *it*.

**Nothing live is held.** No engine, no LanceDB connection, no provider client and no document text:
the conversation holding this agent is pickled between Reflex events. Retrieval goes through
:class:`~gws_ai_toolkit.models.knowledge_base.knowledge_base_retriever.KnowledgeBaseRetriever`, which
builds its engine per call, and the provider key is held as a string.
"""

from collections.abc import AsyncGenerator

from pydantic_ai.models import Model

from gws_ai_toolkit.core.agents.agent_events import (
    BaseFunctionAgentEvent,
    FunctionCallEvent,
    UserQueryTextEvent,
)
from gws_ai_toolkit.core.agents.base_pydantic_agent_ai import AgentToolSpec, BasePydanticAgentAi
from gws_ai_toolkit.models.knowledge_base.knowledge_base_retriever import KnowledgeBaseRetriever
from gws_ai_toolkit.rag.knowledge_base.knowledge_base_models import RetrievedChunk

from .ai_expert_chat_config import AiExpertChatConfig
from .ai_expert_document import AiExpertDocument

# Union of everything an AI Expert run emits: the base response events, and the user query. There is
# no tool event of its own because there is no tool.
AiExpertAgentEvent = BaseFunctionAgentEvent | UserQueryTextEvent

# What a ``relevant_chunks`` run tells the model when the question matched no passage of the document.
# Substituted in place of the document text rather than raised: a question a document does not cover
# is an answer the model can give ("this document does not discuss it"), and failing the turn instead
# would tell the user the chat is broken.
NO_PASSAGE_FOUND_MESSAGE = (
    "No passage of this document matched the question. Tell the user the document does not appear "
    "to cover it, rather than answering from anything else."
)


class AiExpertAgentAi(BasePydanticAgentAi[AiExpertAgentEvent, UserQueryTextEvent]):
    """Answers questions about one document, from its passages or from its whole text.

    Attributes:
        chat_config: The AI Expert configuration a run answers with (mode, prompt, model, ...).
        document: The one document this agent answers about.
        retriever: Where ``relevant_chunks`` retrieves from. Injected, so the agent can be driven
            with no database and no embedding provider.
    """

    chat_config: AiExpertChatConfig
    document: AiExpertDocument
    retriever: KnowledgeBaseRetriever

    def __init__(
        self,
        chat_config: AiExpertChatConfig,
        document: AiExpertDocument,
        retriever: KnowledgeBaseRetriever,
        api_key: str | None = None,
        model: Model | None = None,
    ) -> None:
        """Build an AI Expert agent.

        Args:
            chat_config: The configuration of the AI Expert chat this agent answers for. Its
                ``temperature`` becomes a pydantic-ai model setting, and its ``model`` a
                ``provider:model`` string resolved by ``AiModelFactory``.
            document: The document the conversation is about.
            retriever: Where ``relevant_chunks`` retrieves from. Required in both modes so that a
                mode change mid-conversation needs no new agent, even though ``full_text_chunk``
                never calls it.
            api_key: API key for the configured provider, injected explicitly rather than left to
                the process environment — a Reflex app resolves it from credentials, and a lab that
                never exported ``OPENAI_API_KEY`` must still be able to chat.
            model: A pydantic-ai model overriding ``chat_config.model``. This is the seam tests use
                to substitute ``TestModel`` / ``FunctionModel`` and make no API call.
        """
        super().__init__(
            openai_api_key=api_key,
            model=model or chat_config.model,
            temperature=chat_config.temperature,
        )
        self.chat_config = chat_config
        self.document = document
        self.retriever = retriever

    # ------------------------------------------------------------------ public surface

    def get_document_id(self) -> str:
        """Id of the document this agent answers about, which is what a restore restores from."""
        return self.document.document_id

    # ------------------------------------------------------------------ agent definition

    def _get_ai_instruction(self, user_query: UserQueryTextEvent) -> str:
        """The configured system prompt, with the document's name and text in place of its placeholder.

        Args:
            user_query: The user's question. Its wording *is* the retrieval query in
                ``relevant_chunks`` mode, which is why the instructions are built per run.

        Returns:
            The instructions handed to the model for this run.

        Raises:
            FileNotFoundError: In ``full_text_chunk`` mode, if the snapshot is gone.
            EmptyDocumentError: In ``full_text_chunk`` mode, if no text can be extracted from it.
        """
        document_text = self._get_document_text(user_query.query)
        return self.chat_config.system_prompt.replace(
            self.chat_config.prompt_file_placeholder,
            f"{self.document.filename}\n{document_text}",
        )

    def _get_tools(self) -> list[AgentToolSpec]:
        """No tool at all: AI Expert answers from text it was already given.

        Returns:
            An empty list, which is what makes this a plain streaming agent.
        """
        return []

    async def _handle_function_call(
        self, function_call_event: FunctionCallEvent, user_query: UserQueryTextEvent
    ) -> AsyncGenerator[AiExpertAgentEvent, None]:
        """Never called: the model is offered no tool, so it has none to call.

        Implemented only because the base class declares it abstract, and raising rather than
        returning nothing so that a tool added here without a handler fails loudly instead of
        silently reporting "the function returned no result" to the model.

        Args:
            function_call_event: The tool call that cannot exist.
            user_query: The user's question.

        Raises:
            ValueError: Always.
        """
        raise ValueError(
            f"The AI Expert agent exposes no tool, so '{function_call_event.function_name}' "
            "cannot be executed."
        )
        yield  # type: ignore[unreachable]  # unreachable, and what makes this an async generator

    # ------------------------------------------------------------------ document text

    def _get_document_text(self, question: str) -> str:
        """The document text this mode puts in front of the model.

        Args:
            question: The user's question, used as the retrieval query in ``relevant_chunks`` mode.

        Returns:
            The passages matching the question, or the document's whole text.
        """
        if self.chat_config.mode == "relevant_chunks":
            return self._get_relevant_passages(question)

        return self.document.read_text()

    def _get_relevant_passages(self, question: str) -> str:
        """Retrieve the passages of *this document* that match the question.

        The retrieval is scoped twice: to the knowledge base holding the document, and to the
        document itself. Both are needed — the engine refuses an unscoped search, and without the
        document filter the answer could quote a neighbouring document the user did not open.

        Args:
            question: The retrieval query.

        Returns:
            The matching passages as one block of text, or :data:`NO_PASSAGE_FOUND_MESSAGE`.
        """
        chunks = self.retriever.retrieve(
            query=question,
            knowledge_base_ids=[self.document.knowledge_base_id],
            top_k=self.chat_config.max_chunks,
            document_ids=[self.document.document_id],
        )
        return self._format_passages(chunks)

    @staticmethod
    def _format_passages(chunks: list[RetrievedChunk]) -> str:
        """Render retrieved passages for the model, numbered so it can refer to them.

        The document name is not repeated per passage as it is in the knowledge-base chat: every
        passage here comes from the one document the instructions already name.

        Args:
            chunks: The retrieved chunks, best first.

        Returns:
            The passages as one block of text.
        """
        if not chunks:
            return NO_PASSAGE_FOUND_MESSAGE

        return "\n\n".join(
            f"[{index}] {chunk.content}" for index, chunk in enumerate(chunks, start=1)
        )
