from typing import Any

import reflex as rx
from gws_ai_toolkit.models.chat.chat_conversation import ChatConversation
from gws_ai_toolkit.models.chat.chat_conversation_dto import SaveChatConversationDTO
from gws_ai_toolkit.models.chat.chat_conversation_service import ChatConversationService
from gws_ai_toolkit.models.chat.message import ChatMessageBase, ChatMessageText
from gws_core import Logger
from gws_reflex_main import ReflexMainState

from ..rag_chat.config.rag_config_state import RagConfigState


class ConversationHistoryState(rx.State):
    """State management for conversation history storage using ChatConversationService."""

    # Constants for folder structure
    IMAGES_FOLDER_NAME: str = "images"
    PLOTS_FOLDER_NAME: str = "plots"

    _conversation_service: ChatConversationService | None = None

    def _get_conversation_service(self) -> ChatConversationService:
        """Get the conversation service instance."""
        if not self._conversation_service:
            self._conversation_service = ChatConversationService()
        return self._conversation_service

    async def _get_chat_app_name(self) -> str:
        """Get the chat app name from the app config state."""
        app_config_state = await RagConfigState.get_instance(self)
        return await app_config_state.get_chat_app_name()

    async def save_conversation(
        self,
        conversation_id: str | None,
        messages: list[ChatMessageBase],
        mode: str,
        configuration: dict[str, Any],
        external_conversation_id: str | None = None,
    ) -> ChatConversation | None:
        """Add or update a conversation in the history using ChatConversationService.

        Args:
            conversation_id: Unique identifier for the conversation
            messages: List of chat messages in the conversation
            mode: Mode of the conversation (e.g., "RAG", "ai_expert")
            configuration: Configuration settings (mode, temperature, expert_mode, document_id, etc.)
            external_conversation_id: Optional ID from external system (openai, dify, ragflow...)
        """
        try:
            # Get chat app name
            chat_app_name = await self._get_chat_app_name()

            conversation_service = self._get_conversation_service()

            # Generate label from first user message
            label = ""
            for message in messages:
                if message.role == "user" and message.type == "text":
                    if isinstance(message, ChatMessageText):
                        label_text = str(message.content).strip()[:100]
                        if len(str(message.content).strip()) > 100:
                            label_text += "..."
                        label = label_text
                        break

            conversation_dto = SaveChatConversationDTO(
                id=conversation_id,
                chat_app_name=chat_app_name,
                configuration=configuration,
                mode=mode,
                label=label,
                external_conversation_id=external_conversation_id,
                messages=messages,
            )

            main_state = await self.get_state(ReflexMainState)
            with await main_state.authenticate_user():
                # Create conversation
                return conversation_service.save_conversation(conversation_dto)

        except Exception as e:
            Logger.log_exception_stack_trace(e)
            return None
