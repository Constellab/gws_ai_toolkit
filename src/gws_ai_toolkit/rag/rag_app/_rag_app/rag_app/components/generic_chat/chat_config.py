import uuid
from abc import abstractmethod
from dataclasses import dataclass
from typing import Callable, List, Optional, Type

import reflex as rx
from gws_ai_toolkit.rag.common.rag_models import RagChunk
from gws_ai_toolkit.rag.rag_app._rag_app.rag_app.components.generic_chat.generic_chat_class import \
    ChatMessage


class ChatStateBase(rx.State, mixin=True):
    """Protocol defining the interface that any chat state must implement"""

    # Required properties
    chat_messages: List[ChatMessage]
    current_response_message: Optional[ChatMessage]
    is_streaming: bool
    conversation_id: Optional[str] = None

    # UI Configuration
    title: str = "AI Chat"
    subtitle: Optional[str] = None
    placeholder_text: str = "Ask something..."
    empty_state_message: str = "Start talking to the AI"
    clear_button_text: str = "Clear History"

    @rx.event(background=True)
    async def submit_input_form(self, form_data: dict) -> None:
        """On chat input form submit, check message and call AI chat

        Args:
            form_data (dict): The form data submitted by the user
        """
        user_message = form_data.get("message", "").strip()
        if not user_message:
            return

        message = ChatMessage(
            role="user",
            content=user_message,
            id=str(uuid.uuid4()),
            sources=[]
        )

        async with self:
            self.chat_messages.append(message)
            self.is_streaming = True

        try:
            await self.call_ai_chat(user_message)
        except Exception as e:
            error_message = ChatMessage(
                role="assistant",
                content=f"Error: {str(e)}",
                id=str(uuid.uuid4()),
                sources=[]
            )
            await self.update_current_response_message(error_message)
            await self.close_current_message()
        finally:
            async with self:
                self.is_streaming = False
            await self.close_current_message()

    async def update_current_response_message(self, message: ChatMessage) -> None:
        """Set the current streaming response message"""
        async with self:
            self.current_response_message = message

    async def update_current_message_sources(self, sources: List[RagChunk]) -> None:
        """Update the sources of the current streaming message"""
        async with self:
            if self.current_response_message:
                self.current_response_message.sources = sources

    async def close_current_message(self):
        """Close the current streaming message and add it to the chat history"""
        async with self:
            if self.current_response_message:
                self.chat_messages.append(self.current_response_message)
                self.current_response_message = None

    @abstractmethod
    async def call_ai_chat(self, user_message: str) -> None: ...

    def set_conversation_id(self, conversation_id: str) -> None:
        self.conversation_id = conversation_id

    @rx.event
    def clear_chat(self) -> None:
        self.chat_messages = []
        self.current_response_message = None
        self.conversation_id = None


@dataclass
class ChatConfig:
    """Simple configuration for chat component - only state is configurable"""

    # State configuration - this is the only customizable part
    state: Type[ChatStateBase]

    # Add custom button on top right of the header
    header_buttons: Callable[[], List[rx.Component]] | None = None
