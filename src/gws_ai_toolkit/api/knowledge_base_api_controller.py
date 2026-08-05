"""The brick's HTTP routes: ``POST /brick/gws_ai_toolkit/chat/ask`` and ``.../chat/stream``.

For the CLI (``gws community ask-chatbot``), the Community website chat, and any other
server-side caller — the Constellab Community backend chief among them. See
``docs/done/knowledge_base_public_api_plan.md`` for the routes' design and
``.knowledge_base_api_service`` for what they delegate to.

Registered through ``ApiRegistry.register_brick_api`` rather than added to the main app: that is
what attaches the lab's CORS policy and security headers on registration, per that module's own
guidance, instead of this brick adding its own middleware.
"""

from fastapi import Depends
from fastapi.responses import StreamingResponse
from gws_core import ApiRegistry

from gws_ai_toolkit.models.knowledge_base.rag_chat_profile import RagChatProfile

from .knowledge_base_api_auth import PublishTokenAuth
from .knowledge_base_api_dto import KnowledgeBaseAskRequest, KnowledgeBaseAskResponse
from .knowledge_base_api_service import KnowledgeBaseApiService

SSE_MEDIA_TYPE = "text/event-stream"
# No intermediary may buffer or cache a chunk of an in-progress answer: `no-cache` for a caching
# proxy, `X-Accel-Buffering: no` for the common case of one sitting in front of uvicorn (nginx).
SSE_HEADERS = {"Cache-Control": "no-cache", "X-Accel-Buffering": "no"}

knowledge_base_api = ApiRegistry.register_brick_api("gws_ai_toolkit")


@knowledge_base_api.post("/chat/ask", summary="Ask a question against a published chat profile")
def ask(
    request: KnowledgeBaseAskRequest,
    profile: RagChatProfile = Depends(PublishTokenAuth.check_auth),
) -> KnowledgeBaseAskResponse:
    """Answer a question, in or continuing a conversation scoped to the token's own profile."""
    return KnowledgeBaseApiService().ask(profile, request)


@knowledge_base_api.post(
    "/chat/stream", summary="Ask a question, streaming the answer as it is generated"
)
def stream(
    request: KnowledgeBaseAskRequest,
    profile: RagChatProfile = Depends(PublishTokenAuth.check_auth),
) -> StreamingResponse:
    """The SSE counterpart of ``ask``: same authorisation, scope and chat loop, streamed as deltas.

    ``KnowledgeBaseApiService.stream`` validates and resolves the conversation before returning —
    a rejected request (bad token already handled by ``profile``, an over-long message, an unowned
    ``session_id``) is a normal error *response*, not a stream that opens and then reports the same
    failure as its first event.
    """
    events = KnowledgeBaseApiService().stream(profile, request)
    return StreamingResponse(events, media_type=SSE_MEDIA_TYPE, headers=SSE_HEADERS)
