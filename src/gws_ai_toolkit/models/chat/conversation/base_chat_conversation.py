from abc import abstractmethod
from collections.abc import Generator
from typing import cast
from uuid import uuid4

from attr import dataclass
from gws_core import UserDTO

from gws_ai_toolkit.models.chat.chat_conversation_dto import SaveChatConversationDTO
from gws_ai_toolkit.models.chat.chat_conversation_service import ChatConversationService
from gws_ai_toolkit.models.chat.message.chat_message_base import ChatMessageBase
from gws_ai_toolkit.models.chat.message.chat_message_source import ChatMessageSource
from gws_ai_toolkit.models.chat.message.chat_message_streaming import ChatMessageStreaming
from gws_ai_toolkit.models.chat.message.chat_message_text import ChatMessageText
from gws_ai_toolkit.models.chat.message.chat_message_types import ChatMessage
from gws_ai_toolkit.rag.common.rag_models import RagChatSource


@dataclass
class BaseChatConversationConfig:
    """Configuration for BaseChatConversation."""

    chat_app_name: str
    user: UserDTO | None = None
    store_conversation_in_db: bool = True


class BaseChatConversation:
    mode: str
    conv_config: BaseChatConversationConfig
    chat_configuration: dict

    chat_messages: list[ChatMessageBase]
    current_response_message: ChatMessageStreaming | None

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
        self._conversation_id = None
        self._conversation_service = ChatConversationService()

    def call_conversation(self, user_message: str) -> Generator[ChatMessage, None, None]:
        """Handle user message and call AI chat service.

        Args:
            user_message (str): The message from the user
        """

        if not self._conversation_id:
            raise ValueError("Conversation has not been created yet.")

        for message in self.call_ai_chat(user_message):
            if isinstance(message, ChatMessageStreaming):
                self.current_response_message = message
            else:
                self.current_response_message = None
            yield message

    @abstractmethod
    def call_ai_chat(self, user_message: str) -> Generator[ChatMessage, None, None]:
        """Handle user message and call AI chat service.

        Args:
            user_message (str): The message from the user
        """

    def create_conversation(self, user_message: str) -> None:
        """Create a new conversation in the database."""

        if self._conversation_id is None:
            conversation_dto = SaveChatConversationDTO(
                chat_app_name=self.conv_config.chat_app_name,
                configuration=self.chat_configuration,
                mode=self.mode,
                label=user_message[:60],
                messages=[],
            )

            self._save_conversation(conversation_dto)

    def add_message(self, message: ChatMessageBase) -> None:
        """Add a message to the conversation."""
        self.chat_messages.append(message)

    def close_current_message(
        self, external_id: str | None = None, sources: list[RagChatSource] | None = None
    ) -> ChatMessage | None:
        if not self._conversation_id:
            raise ValueError("Conversation must be created before saving messages")

        if not self.current_response_message:
            return None

        chat_message: ChatMessageBase
        if sources:
            chat_message = ChatMessageSource(
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
                content=content, external_id=external_id or self.current_response_message.external_id
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
