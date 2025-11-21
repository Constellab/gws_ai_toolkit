
import uuid
from abc import abstractmethod
from typing import List, Optional

import reflex as rx
from anyio import sleep
from gws_ai_toolkit.core.utils import Utils
from gws_ai_toolkit.models.chat.chat_message_dto import (ChatMessageDTO,
                                                         ChatMessageText)
from gws_ai_toolkit.rag.common.rag_models import RagChatSource
from gws_ai_toolkit.rag.common.rag_resource import RagResource
from gws_core import Logger
from gws_reflex_main import ReflexMainState

from ..history.conversation_history_state import ConversationHistoryState


class ChatStateBase(rx.State, mixin=True):
    """Abstract base class for all chat state implementations.

    This class provides the foundation for all chat functionality in the application,
    defining the common interface, state management, and core methods that all chat
    implementations must provide. It handles message management, streaming responses,
    user interactions, and conversation persistence.

    Key Features:
        - Abstract interface for AI chat integration
        - Message management and display
        - Streaming response handling
        - Form submission and validation
        - Conversation history integration
        - Error handling and user feedback
        - Configurable UI properties

    State Attributes:
        chat_messages (List[ChatMessage]): Complete message history
        _current_response_message (Optional[ChatMessage]): Currently streaming message
        is_streaming (bool): Flag indicating if AI is currently responding
        conversation_id (Optional[str]): Unique ID for conversation continuity

    UI Configuration:
        title (str): Chat interface title
        subtitle (Optional[str]): Optional subtitle text
        placeholder_text (str): Input field placeholder
        empty_state_message (str): Message shown when chat is empty
        clear_button_text (str): Text for clear chat button
        show_chat_code_block (bool): Whether to display code blocks

    Abstract Methods:
        call_ai_chat(user_message): Must be implemented by subclasses to handle AI calls

    Usage:
        Subclass this to create specific chat implementations like RAG chat or AI Expert.
        Implement call_ai_chat() to integrate with your specific AI service.
    """

    # Required properties
    chat_messages: List[ChatMessageDTO]
    current_response_message: Optional[ChatMessageDTO]
    is_streaming: bool

    _conversation_id: Optional[str] = None
    external_conversation_id: Optional[str] = None  # ID from external system (openai, dify, ragflow...)

    # UI Configuration
    title: str = "AI Chat"
    subtitle: Optional[str] = None
    placeholder_text: str = "Ask something..."
    empty_state_message: str = "Start talking to the AI"
    clear_button_text: str = "New chat"
    show_chat_code_block: bool = False

    _images_folder: Optional[str] = None
    _plots_folder: Optional[str] = None

    @abstractmethod
    async def call_ai_chat(self, user_message: str) -> None:
        """Handle user message and call AI chat service.

        Args:
            user_message (str): The message from the user
        """

    @abstractmethod
    def _after_chat_cleared(self):
        """Hook called after chat is cleared to reset analysis-specific state"""

    @rx.event(background=True)  # type: ignore
    async def submit_input_form(self, form_data: dict) -> None:
        """On chat input form submit, check message and call AI chat

        Args:
            form_data (dict): The form data submitted by the user
        """
        user_message = form_data.get("message", "").strip()
        if not user_message:
            return

        message = ChatMessageText(
            role="user",
            content=user_message,
            sources=[]
        )

        async with self:
            self.is_streaming = True
            await self.add_message(message)

        await sleep(0.1)  # Allow UI to update before starting streaming
        try:
            await self.call_ai_chat(user_message)
        except Exception as e:
            Logger.log_exception_stack_trace(e)
            error_message = ChatMessageText(
                role="assistant",
                content=f"Error: {str(e)}",
                sources=[]
            )
            await self.update_current_response_message(error_message)
            await self.close_current_message()
        finally:
            async with self:
                self.is_streaming = False
            await self.close_current_message()

    async def update_current_response_message(self, message: ChatMessageDTO) -> None:
        """Set the current streaming response message"""
        if not self.is_streaming:
            return
        async with self:
            self.current_response_message = message

    async def update_current_message_sources(self, sources: List[RagChatSource]) -> None:
        """Update the sources of the current streaming message"""
        if not self.is_streaming:
            return
        async with self:
            if self.current_response_message:
                self.current_response_message.sources = sources

    async def close_current_message(self):
        """Close the current streaming message and add it to the chat history"""
        if not self.current_response_message:
            return
        if self.current_response_message:
            async with self:
                await self.add_message(self.current_response_message)
                self.current_response_message = None

    def set_external_conversation_id(self, external_conversation_id: str) -> None:
        self.external_conversation_id = external_conversation_id

    @rx.event
    def clear_chat(self) -> None:
        self.chat_messages = []
        self.current_response_message = None
        self._conversation_id = None
        self.external_conversation_id = None
        self.is_streaming = False
        self._after_chat_cleared()

    async def add_message(self, message: ChatMessageDTO) -> None:
        """Add a message to the chat history"""
        self.chat_messages.append(message)

    @rx.event
    def open_ai_expert(self, rag_document_id: str):
        """Redirect the user to the AI Expert page."""
        return rx.redirect(f"/ai-expert/{rag_document_id}")

    @rx.event
    async def open_document(self, rag_document_id: str):
        """Redirect the user to an external URL."""

        rag_resource = RagResource.from_document_id(rag_document_id)
        if not rag_resource:
            raise ValueError(f"Resource with ID {rag_document_id} not found")
        return await self.open_document_from_resource(rag_resource.get_id())

    @rx.event
    async def open_document_from_resource(self, resource_id: str):
        """Redirect the user to an external URL."""

        main_state = await self.get_state(ReflexMainState)

        with await main_state.authenticate_user():
            public_link = Utils.generate_temp_share_resource_link(resource_id)

        if public_link:
            # Redirect the user to the share link URL
            return rx.redirect(public_link, is_external=True)

    @rx.var
    async def has_no_message(self) -> bool:
        """Check if there are no messages in the chat."""
        return len(self.chat_messages) == 0 and not self.current_response_message and not self.is_streaming

    async def save_conversation_to_history(self, mode: str, configuration: dict):
        """Save the current conversation to history with the given configuration."""
        if not self.chat_messages:
            return

        try:
            async with self:
                history_state = await self.get_state(ConversationHistoryState)
                conversation = await history_state.save_conversation(
                    conversation_id=self._conversation_id,
                    messages=self.chat_messages,
                    mode=mode,
                    configuration=configuration,
                    external_conversation_id=self.external_conversation_id
                )

                if conversation:
                    self._conversation_id = conversation.id
        except Exception as e:
            Logger.error(f"Error saving conversation to history: {e}")
            Logger.log_exception_stack_trace(e)
