"""The wire contract of ``POST /brick/gws_ai_toolkit/chat/ask``.

Field names match what the Constellab Community backend's existing RAGFlow client already sends
and expects (see ``docs/todo/knowledge_base_public_api_plan.md`` § Endpoints), so repointing that
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
