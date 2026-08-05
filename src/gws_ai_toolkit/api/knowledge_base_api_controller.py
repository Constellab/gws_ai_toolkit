"""The brick's first HTTP route: ``POST /brick/gws_ai_toolkit/chat/ask``.

For the CLI (``gws community ask-chatbot``) and any other server-side caller — the Constellab
Community backend chief among them. See ``docs/todo/knowledge_base_public_api_plan.md`` for the
route's design and ``.knowledge_base_api_service`` for what it delegates to.

Registered through ``ApiRegistry.register_brick_api`` rather than added to the main app: that is
what attaches the lab's CORS policy and security headers on registration, per that module's own
guidance, instead of this brick adding its own middleware.
"""

from fastapi import Depends
from gws_core import ApiRegistry

from gws_ai_toolkit.models.knowledge_base.rag_chat_profile import RagChatProfile

from .knowledge_base_api_auth import PublishTokenAuth
from .knowledge_base_api_dto import KnowledgeBaseAskRequest, KnowledgeBaseAskResponse
from .knowledge_base_api_service import KnowledgeBaseApiService

knowledge_base_api = ApiRegistry.register_brick_api("gws_ai_toolkit")


@knowledge_base_api.post("/chat/ask", summary="Ask a question against a published chat profile")
def ask(
    request: KnowledgeBaseAskRequest,
    profile: RagChatProfile = Depends(PublishTokenAuth.check_auth),
) -> KnowledgeBaseAskResponse:
    """Answer a question, in or continuing a conversation scoped to the token's own profile."""
    return KnowledgeBaseApiService().ask(profile, request)
