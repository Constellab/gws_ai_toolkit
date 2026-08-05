"""Authenticating a public chat-API request against a chat profile's publish token.

Publishing is a property of a chat profile, and **the token is the scope** (see
``docs/todo/knowledge_base_public_api_plan.md`` § Authorisation). There is no caller-supplied
profile or knowledge-base id anywhere in the request — the token is the only thing a caller
presents, and it resolves to exactly the profile that minted it.

Every failure mode — a missing header, a malformed scheme, an unknown token, a token whose profile
was since un-published — is rejected with the same message. Distinguishing them in the response
would let a caller probe which tokens once existed; a public endpoint gives none of them anything
to learn from.
"""

from fastapi import Request
from fastapi.security.utils import get_authorization_scheme_param
from gws_core import ForbiddenException

from gws_ai_toolkit.models.knowledge_base.rag_chat_profile import RagChatProfile

from .knowledge_base_api_rate_limiter import KnowledgeBaseApiRateLimiter

INVALID_TOKEN_MESSAGE = "Invalid or revoked publish token."


class PublishTokenAuth:
    """FastAPI dependency: a valid ``Authorization: Bearer <token>`` header resolves a profile."""

    BEARER_SCHEME = "bearer"

    # Rate limiting ships with authentication, not after it (see the rate limiter's own module
    # docstring): a request that never resolves a valid token never reaches this counter, so the
    # cap only ever throttles calls a real publish token is paying for.
    _rate_limiter = KnowledgeBaseApiRateLimiter()

    @classmethod
    def check_auth(cls, request: Request) -> RagChatProfile:
        """Resolve and return the profile this request's token authenticates.

        :param request: the incoming request, read for its ``Authorization`` header
        :raises ForbiddenException: if the header is missing, malformed, or names a token that
                does not authenticate a currently published profile
        :raises BaseHTTPException: with a 429 status, if this token has exceeded its request cap
        :return: the profile the token belongs to
        """
        token = cls._get_and_check_token(request)

        profile = RagChatProfile.get_by_publish_token(token)
        if profile is None or not profile.is_published:
            raise ForbiddenException(INVALID_TOKEN_MESSAGE)

        cls._rate_limiter.check(token)
        return profile

    @classmethod
    def _get_and_check_token(cls, request: Request) -> str:
        """The bearer token carried by the request's ``Authorization`` header.

        :raises ForbiddenException: if the header is absent or is not a well-formed bearer token
        """
        header_authorization = request.headers.get("Authorization")
        scheme, token = get_authorization_scheme_param(header_authorization)

        if scheme.lower() != cls.BEARER_SCHEME or not token:
            raise ForbiddenException(INVALID_TOKEN_MESSAGE)

        return token
