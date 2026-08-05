"""Answering a question through the public chat API, on the same chat loop the Reflex UI drains.

This is the non-streaming half of ``docs/todo/knowledge_base_public_api_plan.md`` § Endpoints. It
reuses :class:`~gws_ai_toolkit.models.knowledge_base.knowledge_base_chat_factory.KnowledgeBaseChatFactory`
and :meth:`~gws_ai_toolkit.models.chat.conversation.base_chat_conversation.BaseChatConversation.call_conversation`
exactly as the chat window does — there is one chat loop, not a second one written for HTTP.

What is specific to this boundary, kept out of the factory and the conversation:

- **Conversation ownership.** A supplied ``session_id`` must belong to the token's own profile.
  Whether that is true for any *other* reason (wrong mode, deleted profile, unknown id) is reported
  with the same generic message as "belongs to another profile" — a public endpoint gives a caller
  nothing to learn from a session id it does not own.
- **Attribution.** Conversations the route creates are attributed to the system user (see
  ``docs/todo/knowledge_base_public_api_plan.md`` § Conversation ownership) — external callers have
  no lab user, and ``ChatConversation.user`` is a plain, non-null FK.
- **Cost bounds.** A message length cap, and a cap on how many of a conversation's own past turns
  are replayed into the model on each call — both from § Rate limiting of the same plan.
"""

from fastapi import status
from gws_core import AuthenticateUser, BadRequestException, BaseHTTPException, NotFoundException
from gws_core import User as GwsCoreUser

from gws_ai_toolkit.models.chat.conversation.knowledge_base_chat_conversation import (
    KnowledgeBaseChatConversation,
)
from gws_ai_toolkit.models.chat.message.chat_message_base import ChatMessageBase
from gws_ai_toolkit.models.chat.message.chat_message_error import ChatMessageError
from gws_ai_toolkit.models.chat.message.chat_message_source import ChatMessageSource
from gws_ai_toolkit.models.chat.message.chat_message_streaming import ChatMessageStreaming
from gws_ai_toolkit.models.chat.message.chat_message_types import ChatMessage
from gws_ai_toolkit.models.chat.message.chat_user_message import ChatUserMessageText
from gws_ai_toolkit.models.knowledge_base.knowledge_base_chat_factory import (
    KnowledgeBaseChatFactory,
    KnowledgeBaseChatUnavailableError,
)
from gws_ai_toolkit.models.knowledge_base.knowledge_base_retriever import (
    EngineKnowledgeBaseRetriever,
)
from gws_ai_toolkit.models.knowledge_base.rag_chat_profile import RagChatProfile
from gws_ai_toolkit.rag.knowledge_base.knowledge_base_config import (
    DEFAULT_OPENAI_EMBEDDING_MODEL,
    EmbeddingConfig,
    EmbeddingProvider,
)
from gws_ai_toolkit.rag.knowledge_base.knowledge_base_credentials import resolve_openai_api_key

from .knowledge_base_api_dto import KnowledgeBaseAskRequest, KnowledgeBaseAskResponse

# The chat app external conversations belong to — distinct from any Reflex app's own name, so a
# route-created conversation is identifiable as such in a listing.
CHAT_APP_NAME = "knowledge_base_public_api"

# Cheap and unsophisticated on purpose (see the module docstring's "Cost bounds"): a request costs
# an embedding plus an LLM completion regardless of how long the message is, so a long message
# buys nothing but a bigger bill for a leaked token.
MAX_MESSAGE_LENGTH = 4000

# How many of a conversation's own past questions are replayed into the model on each call. A long
# conversation must not make every new question more expensive than the last.
MAX_REPLAYED_TURNS = 10

UNKNOWN_SESSION_MESSAGE = "Unknown session_id, or it does not belong to this token's profile."
MESSAGE_TOO_LONG_MESSAGE = f"message exceeds the maximum length of {MAX_MESSAGE_LENGTH} characters."


class KnowledgeBaseApiService:
    """Runs one question against a chat profile, for :mod:`.knowledge_base_api_controller`."""

    def ask(
        self,
        profile: RagChatProfile,
        request: KnowledgeBaseAskRequest,
        factory: KnowledgeBaseChatFactory | None = None,
    ) -> KnowledgeBaseAskResponse:
        """Answer ``request.message`` against ``profile``, creating or continuing a conversation.

        :param profile: the profile the caller's publish token resolved to — never a
                        caller-supplied id (see the module docstring)
        :param request: the question, and the conversation to continue if any
        :param factory: overrides the lab's default factory — the seam tests use to substitute a
                        scripted model and a stub retriever, so no API call is ever made
        :raises BadRequestException: if the message is too long, or ``session_id`` does not name a
                conversation belonging to this profile
        :raises BaseHTTPException: with a 502 status, if the chat run itself failed
        """
        self._check_message_length(request.message)

        with AuthenticateUser(GwsCoreUser.get_and_check_sysuser()):
            factory = factory or self._build_factory()
            conversation = self._get_or_restore_conversation(factory, profile, request)
            final_message = self._drain(conversation, request.message)
            return self._build_response(conversation, final_message)

    ############################################### CONVERSATION ###############################################

    def _get_or_restore_conversation(
        self,
        factory: KnowledgeBaseChatFactory,
        profile: RagChatProfile,
        request: KnowledgeBaseAskRequest,
    ) -> KnowledgeBaseChatConversation:
        if request.session_id is None:
            conversation = factory.build_conversation(profile.id)
            conversation.create_conversation(request.message[:60])
            return conversation

        conversation = self._restore_owned_conversation(factory, profile, request.session_id)
        self._cap_replayed_turns(conversation)
        return conversation

    def _restore_owned_conversation(
        self, factory: KnowledgeBaseChatFactory, profile: RagChatProfile, session_id: str
    ) -> KnowledgeBaseChatConversation:
        """Reopen ``session_id``, refusing it unless it is a knowledge-base conversation of ``profile``."""
        try:
            conversation = factory.restore_conversation(session_id)
        except (NotFoundException, KnowledgeBaseChatUnavailableError) as error:
            raise BadRequestException(UNKNOWN_SESSION_MESSAGE) from error

        if conversation.knowledge_agent.get_chat_profile_id() != profile.id:
            raise BadRequestException(UNKNOWN_SESSION_MESSAGE)

        return conversation

    def _cap_replayed_turns(self, conversation: KnowledgeBaseChatConversation) -> None:
        """Trim the history handed back to the model to the last :data:`MAX_REPLAYED_TURNS` turns."""
        capped = self._last_turns(conversation.chat_messages, MAX_REPLAYED_TURNS)
        if len(capped) != len(conversation.chat_messages):
            conversation.restore_messages(capped)

    @staticmethod
    def _last_turns(messages: list[ChatMessageBase], max_turns: int) -> list[ChatMessageBase]:
        """The messages of the last ``max_turns`` user turns onward, or all of them if fewer.

        Cutting at a user-message boundary — rather than at a plain message count — never starts
        the replayed history mid tool-call/tool-result pair.
        """
        user_turn_indices = [index for index, message in enumerate(messages) if message.is_user_message()]
        if len(user_turn_indices) <= max_turns:
            return messages
        return messages[user_turn_indices[-max_turns] :]

    ############################################### RUN ###############################################

    def _drain(self, conversation: KnowledgeBaseChatConversation, message: str) -> ChatMessage | None:
        """Run the question through the shared chat loop, keeping only its final visible message."""
        user_message = ChatUserMessageText(content=message)

        final_message: ChatMessage | None = None
        for chat_message in conversation.call_conversation(user_message):
            if isinstance(chat_message, ChatMessageStreaming) or chat_message.is_history_only():
                continue
            final_message = chat_message

        return final_message

    def _build_response(
        self, conversation: KnowledgeBaseChatConversation, final_message: ChatMessage | None
    ) -> KnowledgeBaseAskResponse:
        """The response contract, from the chat loop's final message.

        :raises BaseHTTPException: with a 502 status, if the run produced no answer or ended on an
                error — a truncated or missing answer is never presented as a complete one
        """
        if final_message is None:
            raise BaseHTTPException(status.HTTP_502_BAD_GATEWAY, "The chat produced no answer.")
        if isinstance(final_message, ChatMessageError):
            raise BaseHTTPException(status.HTTP_502_BAD_GATEWAY, final_message.error)

        references = final_message.sources if isinstance(final_message, ChatMessageSource) else []
        return KnowledgeBaseAskResponse(
            answer=final_message.content,
            session_id=conversation.conversation_id,
            references=references or [],
        )

    ############################################### CONFIGURATION ###############################################

    def _check_message_length(self, message: str) -> None:
        if len(message) > MAX_MESSAGE_LENGTH:
            raise BadRequestException(MESSAGE_TOO_LONG_MESSAGE)

    def _build_factory(self) -> KnowledgeBaseChatFactory:
        """A factory using the lab's default embedding and chat configuration.

        There is no Reflex app instance behind this route to read app params from (see
        ``KnowledgeBaseAppState`` for where the Reflex chat window reads its own), so this uses the
        same defaults that state falls back to: OpenAI embeddings at the default model, and the
        lab-wide API key. A lab whose Reflex app overrides the embedding provider or model via app
        params is not served correctly by this route yet — a known limitation, not an oversight.
        """
        api_key = resolve_openai_api_key(None)
        embedding_config = EmbeddingConfig(
            provider=EmbeddingProvider.OPENAI,
            model=DEFAULT_OPENAI_EMBEDDING_MODEL,
            api_key=api_key,
        )
        return KnowledgeBaseChatFactory(
            chat_app_name=CHAT_APP_NAME,
            retriever=EngineKnowledgeBaseRetriever(embedding_config),
            api_key=api_key,
        )
