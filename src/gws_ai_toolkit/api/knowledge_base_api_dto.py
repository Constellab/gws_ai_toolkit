"""The wire contract of ``POST /brick/gws_ai_toolkit/chat/ask``.

Field names match what the Constellab Community backend's existing RAGFlow client already sends
and expects (see ``docs/done/knowledge_base_public_api_plan.md`` § Endpoints), so repointing that
client at this route is a rename rather than a rewrite.
"""

from gws_core import BaseModelDTO

from gws_ai_toolkit.rag.common.rag_models import RagChatSource


class KnowledgeBaseAskRequest(BaseModelDTO):
    """A question against the profile the caller's publish token resolves to.

    Attributes:
        message: The question to ask.
        session_id: The conversation to continue, or ``None`` to start a new one. Must belong to
            the token's own profile — see
            :meth:`~gws_ai_toolkit.api.knowledge_base_api_service.KnowledgeBaseApiService.ask`.
    """

    message: str
    session_id: str | None = None


class KnowledgeBaseAskResponse(BaseModelDTO):
    """The answer to a :class:`KnowledgeBaseAskRequest`.

    Attributes:
        answer: The final assistant message's text.
        session_id: The conversation's id — pass it back as the next request's ``session_id`` to
            continue the conversation.
        references: The sources the answer was attributed to, empty when the answer cited none.
    """

    answer: str
    session_id: str
    references: list[RagChatSource] = []


class KnowledgeBaseStreamDeltaEvent(BaseModelDTO):
    """An ``event: delta`` of ``POST /brick/gws_ai_toolkit/chat/stream`` — one chunk of the answer.

    Deltas arrive in generation order; concatenating every ``content`` in order rebuilds the same
    text :class:`KnowledgeBaseAskResponse` would have returned as ``answer``.

    Attributes:
        content: The text to append to the answer built so far.
    """

    content: str


class KnowledgeBaseStreamDoneEvent(BaseModelDTO):
    """The ``event: done`` closing a successful stream.

    Carries what the deltas could not: the two fields :class:`KnowledgeBaseAskResponse` returns
    alongside ``answer``, which the deltas already spelled out.

    Attributes:
        session_id: The conversation's id, as in :class:`KnowledgeBaseAskResponse`.
        references: The sources the answer was attributed to, as in :class:`KnowledgeBaseAskResponse`.
    """

    session_id: str
    references: list[RagChatSource] = []


class KnowledgeBaseStreamErrorEvent(BaseModelDTO):
    """The ``event: error`` closing a failed stream — never a partial answer presented as complete.

    Attributes:
        error: What went wrong.
    """

    error: str
