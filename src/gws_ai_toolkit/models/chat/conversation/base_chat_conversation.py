from abc import ABC, abstractmethod
from collections.abc import Generator
from enum import Enum
from typing import Generic, TypeVar, cast
from uuid import uuid4

from attr import dataclass
from gws_core import BaseModelDTO, UserDTO

from gws_ai_toolkit.core.agents.agent_events import (
    FunctionCallEvent,
    FunctionErrorEvent,
    FunctionSuccessEvent,
)
from gws_ai_toolkit.models.chat.chat_conversation_dto import SaveChatConversationDTO
from gws_ai_toolkit.models.chat.chat_conversation_service import ChatConversationService
from gws_ai_toolkit.models.chat.message.chat_message_base import ChatMessageBase
from gws_ai_toolkit.models.chat.message.chat_message_source import ChatMessageSource
from gws_ai_toolkit.models.chat.message.chat_message_streaming import ChatMessageStreaming
from gws_ai_toolkit.models.chat.message.chat_message_text import ChatMessageText
from gws_ai_toolkit.models.chat.message.chat_message_tool_call import ChatMessageToolCall
from gws_ai_toolkit.models.chat.message.chat_message_tool_result import ChatMessageToolResult
from gws_ai_toolkit.models.chat.message.chat_message_types import ChatMessage
from gws_ai_toolkit.models.chat.message.chat_user_message import ChatUserMessageBase
from gws_ai_toolkit.rag.common.rag_models import RagChatSource


class ChatConversationMode(Enum):
    """What kind of chat a conversation row holds.

    ``RAG`` is **legacy-only**: it belongs to conversations run against the retired RAGFlow / Dify
    datasets. Those rows stay listable in history, but their configuration points at datasets that no
    longer exist, so a restore must report :data:`LEGACY_CONVERSATION_MODE_MESSAGE` rather than fail
    opaquely. The embedded knowledge-base stack uses ``KNOWLEDGE_BASE`` and never reuses ``"rag"``.
    """

    RAG = "rag"
    AI_EXPERT = "ai_expert"
    AI_TABLE = "ai_table"
    KNOWLEDGE_BASE = "knowledge_base"

    @property
    def is_legacy(self) -> bool:
        """True for a mode kept only so that existing rows keep parsing."""
        return self is ChatConversationMode.RAG


# What to show instead of restoring a conversation whose mode is legacy.
LEGACY_CONVERSATION_MODE_MESSAGE = "This conversation used a retired engine and cannot be continued."


@dataclass
class BaseChatConversationConfig:
    """Configuration for BaseChatConversation."""

    chat_app_name: str
    user: UserDTO | None = None
    store_conversation_in_db: bool = True


U = TypeVar("U", bound=ChatUserMessageBase)


class BaseChatConversation(ABC, Generic[U]):
    mode: str
    conv_config: BaseChatConversationConfig
    chat_configuration: dict

    chat_messages: list[ChatMessageBase]
    current_response_message: ChatMessageStreaming | None

    # Tool name of every recorded call, keyed by call id: a tool result names the tool it answers,
    # and only the call carries that name.
    _tool_names_by_call_id: dict[str, str]

    _conversation_id: str | None = None
    _external_conversation_id: str | None = None

    _conversation_service: ChatConversationService

    def __init__(
        self,
        config: BaseChatConversationConfig,
        mode: str,
        chat_configuration: dict | None = None,
    ) -> None:
        self.conv_config = config
        self.mode = mode
        self.chat_configuration = chat_configuration or {}
        self.chat_messages = []
        self.current_response_message = None
        self._tool_names_by_call_id = {}
        self._conversation_id = None
        self._conversation_service = ChatConversationService()

    @property
    def conversation_id(self) -> str | None:
        """The id of this conversation's persisted row, or ``None`` before the first message.

        The public counterpart of ``_conversation_id`` for callers outside this package — the HTTP
        route needs it as the ``session_id`` it hands back, and reaching into a leading-underscore
        attribute is not a seam an external caller should depend on.
        """
        return self._conversation_id

    def call_conversation(self, user_message: U) -> Generator[ChatMessage, None, None]:
        """Handle user message and call AI chat service.

        Args:
            user_message (U): The message from the user
        """

        if not self._conversation_id:
            raise ValueError("Conversation has not been created yet.")

        self.save_message(user_message)

        for message in self._call_ai_chat(user_message):
            if isinstance(message, ChatMessageStreaming):
                self.current_response_message = message
            else:
                self.current_response_message = None
            yield message

    @abstractmethod
    def _call_ai_chat(self, user_message: U) -> Generator[ChatMessage, None, None]:
        """Handle user message and call AI chat service.

        Args:
            user_message (str): The message from the user
        """

    def create_conversation(self, label: str) -> None:
        """Create a new conversation in the database."""

        if self._conversation_id is None:
            conversation_dto = SaveChatConversationDTO(
                chat_app_name=self.conv_config.chat_app_name,
                configuration=self.chat_configuration,
                mode=self.mode,
                label=label,
                messages=[],
            )

            self._save_conversation(conversation_dto)

    def add_message(self, message: ChatMessageBase) -> None:
        """Add a message to the conversation."""
        self.chat_messages.append(message)

    def get_visible_messages(self) -> list[ChatMessageBase]:
        """Get the messages that belong in the visible transcript.

        `chat_messages` also holds history-only messages — the tool calls and tool results kept
        so a restored conversation can rebuild what the model saw. Anything rendering the
        conversation reads this instead.

        Returns:
            list[ChatMessageBase]: The messages to render, in conversation order.
        """
        return ChatMessageBase.filter_visible(self.chat_messages)

    def save_tool_call(
        self,
        tool_name: str,
        args: dict,
        tool_call_id: str,
        external_id: str | None = None,
    ) -> None:
        """Record a tool call the model made, so a restored conversation can replay it.

        Recorded as it happens rather than at the end of the run: the rebuilt history replays
        messages in the order they were saved, and a tool call belongs *before* the answer it
        led to.

        Args:
            tool_name: Name of the tool the model called.
            args: Arguments the model passed.
            tool_call_id: The provider's call id, pairing this call with its result.
            external_id: Optional id of the response that made the call.
        """
        self.save_message(
            ChatMessageToolCall(
                tool_name=tool_name,
                args=args,
                tool_call_id=tool_call_id,
                external_id=external_id,
            )
        )

    def save_tool_result(
        self,
        tool_name: str,
        content: str,
        tool_call_id: str,
        external_id: str | None = None,
    ) -> None:
        """Record what a tool reported back to the model.

        Saved for a failed tool too, carrying the error the model was asked to correct: that is
        what the model was told, and it keeps every recorded call paired with a result.

        Args:
            tool_name: Name of the tool that ran.
            content: What the tool reported back to the model.
            tool_call_id: The provider's call id, pairing this result with its call.
            external_id: Optional id of the response that made the call.
        """
        self.save_message(
            ChatMessageToolResult(
                tool_name=tool_name,
                content=content,
                tool_call_id=tool_call_id,
                external_id=external_id,
            )
        )

    def record_tool_turn(self, event: BaseModelDTO) -> None:
        """Persist the tool turn an agent event carries, if it carries one.

        This is the reverse of
        :class:`~gws_ai_toolkit.models.chat.conversation.chat_message_history_mapper.ChatMessageHistoryMapper`
        and it has to happen *in stream order*, interleaved with the visible messages of the same
        turn, which is why the conversation owns it: the rebuilt history replays messages in the
        order they were saved, and a tool call belongs before the answer it led to.

        Called for every event of a conversation's own agent. Events carrying no tool turn — text
        deltas, response boundaries, whatever a tool produced — are ignored, so a caller can hand
        the whole stream over without filtering it first.

        Args:
            event: The event being handled.
        """
        if isinstance(event, FunctionCallEvent):
            self._tool_names_by_call_id[event.call_id] = event.function_name
            self.save_tool_call(
                tool_name=event.function_name,
                args=event.arguments,
                tool_call_id=event.call_id,
                external_id=event.response_id,
            )

        elif isinstance(event, FunctionSuccessEvent):
            self._save_tool_result_for_call(
                event.call_id, event.function_response, event.response_id
            )

        elif isinstance(event, FunctionErrorEvent):
            # The model was handed this error and asked to correct itself, so it is the result of
            # that call as far as the history is concerned. Recording it keeps the call paired,
            # which a run that recovered from a tool error would otherwise leave dangling.
            self._save_tool_result_for_call(event.call_id, event.message, event.response_id)

    def _save_tool_result_for_call(
        self, call_id: str, content: str, response_id: str | None
    ) -> None:
        """Persist a tool result, resolving the tool name from the call it answers.

        Args:
            call_id: The call this result answers.
            content: What the tool reported back to the model.
            response_id: Id of the response that made the call.
        """
        tool_name = self._tool_names_by_call_id.get(call_id)
        if not tool_name:
            # A result with no recorded call cannot be paired, and an unpaired result is dropped
            # on restore anyway.
            return

        self.save_tool_result(
            tool_name=tool_name,
            content=content,
            tool_call_id=call_id,
            external_id=response_id,
        )

    def restore_messages(self, messages: list[ChatMessageBase]) -> None:
        """Restore a conversation's messages, rebuilding what the model already saw.

        Args:
            messages: The conversation's persisted messages, oldest first.
        """
        self.chat_messages = list(messages)
        self._tool_names_by_call_id = {
            message.tool_call_id: message.tool_name
            for message in messages
            if isinstance(message, ChatMessageToolCall)
        }
        self._restore_agent_history(messages)

    def _restore_agent_history(self, messages: list[ChatMessageBase]) -> None:
        """Hook for subclasses to rebuild their agent's client-side message history.

        Conversations whose agent keeps no history — those talking to a service that holds the
        conversation on its side — need nothing here.

        Args:
            messages: The conversation's persisted messages, oldest first.
        """

    def close_current_message(
        self, external_id: str | None = None, sources: list[RagChatSource] | None = None
    ) -> ChatMessage | None:
        if not self._conversation_id:
            raise ValueError("Conversation must be created before saving messages")

        if not self.current_response_message:
            return None

        chat_message: ChatMessageBase
        if sources:
            chat_message = ChatMessageSource.create_with_updated_source_ids(
                content=self.current_response_message.content,
                external_id=external_id or self.current_response_message.external_id,
                sources=sources,
            )
        else:
            chat_message = ChatMessageText(
                content=self.current_response_message.content,
                external_id=external_id or self.current_response_message.external_id,
            )

        saved_message = self.save_message(chat_message)

        self.current_response_message = None

        return saved_message

    def build_current_message(
        self, content: str, append: bool = True, external_id: str | None = None
    ) -> ChatMessageStreaming:
        """Update the current streaming response message."""
        if self.current_response_message is None:
            # Create new message for streaming
            return ChatMessageStreaming(content=content, external_id=external_id)

        if append:
            return ChatMessageStreaming(
                content=self.current_response_message.content + content,
                external_id=external_id or self.current_response_message.external_id,
            )
        else:
            return ChatMessageStreaming(
                content=content,
                external_id=external_id or self.current_response_message.external_id,
            )

    def _save_conversation(self, conversation_dto: SaveChatConversationDTO) -> None:
        """Save conversation to the database."""

        if self.conv_config.store_conversation_in_db:
            conversation = self._conversation_service.save_conversation(conversation_dto)
            self._conversation_id = conversation.id
        else:
            self._conversation_id = str(uuid4())

    def set_conversation_external_id(self, external_conversation_id: str) -> None:
        """Set the external conversation ID for the current conversation."""
        if self.conv_config.store_conversation_in_db:
            if not self._conversation_id:
                raise ValueError("Conversation must be created before setting external ID")

            self._conversation_service.set_conversation_external_id(
                conversation_id=self._conversation_id,
                external_id=external_conversation_id,
            )

        self._external_conversation_id = external_conversation_id

    def save_message(self, message: ChatMessageBase) -> ChatMessage:
        """Save a message to the conversation in the database."""

        if self.conv_config.store_conversation_in_db:
            if not self._conversation_id:
                raise ValueError("Conversation must be created before saving messages")

            message = self._conversation_service.save_message(
                conversation_id=self._conversation_id,
                message=message,
            )
        else:
            # keep it local
            message.id = str(uuid4())
            message.user = self.conv_config.user

        self.add_message(message)
        return cast(ChatMessage, message)
