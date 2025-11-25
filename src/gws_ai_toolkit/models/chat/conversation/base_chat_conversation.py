from abc import abstractmethod
from collections.abc import Generator

from gws_ai_toolkit.models import (
    AllChatMessages,
    AssistantStreamingResponse,
    ChatMessageBase,
    ChatMessageText,
    ChatUserMessageText,
)
from gws_ai_toolkit.models.chat.chat_conversation import ChatConversation
from gws_ai_toolkit.models.chat.chat_conversation_dto import SaveChatConversationDTO
from gws_ai_toolkit.models.chat.chat_conversation_service import ChatConversationService
from gws_ai_toolkit.rag.common.rag_models import RagChatSource


class BaseChatConversation:
    chat_app_name: str
    configuration: dict
    mode: str

    chat_messages: list[ChatMessageBase]
    current_response_message: AssistantStreamingResponse | None

    _conversation: ChatConversation | None

    _conversation_service: ChatConversationService

    def __init__(self, chat_app_name: str, configuration: dict, mode: str) -> None:
        self.chat_app_name = chat_app_name
        self.configuration = configuration
        self.mode = mode
        self.chat_messages = []
        self.current_response_message = None
        self._conversation = None
        self._conversation_service = ChatConversationService()

    def call_conversation(self) -> Generator[AllChatMessages, None, None]:
        """Handle user message and call AI chat service.

        Args:
            user_message (str): The message from the user
        """

        if not self._conversation:
            raise ValueError("Conversation has not been created yet.")

        last_message = self.chat_messages[-1]
        if not last_message or not isinstance(last_message, ChatUserMessageText):
            raise ValueError("Last message is not a user message.")

        for message in self.call_ai_chat(last_message.content):
            if isinstance(message, AssistantStreamingResponse):
                self.current_response_message = message
            else:
                self.add_message(message)
                self.current_response_message = None
            yield message

    @abstractmethod
    def call_ai_chat(self, user_message: str) -> Generator[AllChatMessages, None, None]:
        """Handle user message and call AI chat service.

        Args:
            user_message (str): The message from the user
        """

    def create_conversation(self, user_message: str) -> None:
        """Create a new conversation in the database."""

        if self._conversation is None:
            conversation_dto = SaveChatConversationDTO(
                chat_app_name=self.chat_app_name,
                configuration=self.configuration,
                mode=self.mode,
                label=user_message[:60],
                messages=[],
            )

            self._conversation = self._conversation_service.save_conversation(conversation_dto)

        user_text_message = ChatUserMessageText(content=user_message)
        message = self._conversation_service.save_message(self._conversation.id, message=user_text_message)

        self.add_message(message)

    def add_message(self, message: ChatMessageBase) -> None:
        """Add a message to the conversation."""
        self.chat_messages.append(message)

    def close_current_message(
        self, external_id: str | None = None, sources: list[RagChatSource] | None = None
    ) -> ChatMessageBase | None:
        if not self._conversation:
            raise ValueError("Conversation must be created before saving messages")

        if not self.current_response_message:
            return None

        # Save the message using the conversation service
        text_message = ChatMessageText(
            content=self.current_response_message.content,
            external_id=external_id or self.current_response_message.external_id,
            sources=sources,
        )
        saved_message = self._conversation_service.save_message(
            conversation_id=self._conversation.id,
            message=text_message,
        )

        self.current_response_message = None

        return saved_message

    def build_current_message(
        self, content: str, append: bool = True, external_id: str | None = None
    ) -> AssistantStreamingResponse:
        """Update the current streaming response message."""
        if self.current_response_message is None:
            # Create new message for streaming
            return AssistantStreamingResponse(content=content, external_id=external_id)

        if append:
            return AssistantStreamingResponse(
                content=self.current_response_message.content + content,
                external_id=external_id or self.current_response_message.external_id,
            )
        else:
            return AssistantStreamingResponse(
                content=content, external_id=external_id or self.current_response_message.external_id
            )
