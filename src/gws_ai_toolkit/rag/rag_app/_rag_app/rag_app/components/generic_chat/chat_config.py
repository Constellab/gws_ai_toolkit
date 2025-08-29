import uuid
from abc import abstractmethod
from dataclasses import dataclass
from typing import Callable, List, Optional, Type

import reflex as rx
from gws_ai_toolkit.rag.common.rag_models import RagChunk
from gws_ai_toolkit.rag.common.rag_resource import RagResource
from gws_ai_toolkit.rag.rag_app._rag_app.rag_app.components.app_config.app_config_state import \
    AppConfigState
from gws_ai_toolkit.rag.rag_app._rag_app.rag_app.components.generic_chat.generic_chat_class import (
    ChatMessage, ChatMessageCode, ChatMessageImage, ChatMessageText)
from gws_core import (AuthenticateUser, GenerateShareLinkDTO,
                      ShareLinkEntityType, ShareLinkService)
from gws_core.core.utils.logger import Logger
from PIL import Image


class ChatStateBase(rx.State, mixin=True):
    """Protocol defining the interface that any chat state must implement"""

    # Required properties
    _chat_messages: List[ChatMessage]
    _current_response_message: Optional[ChatMessage]
    is_streaming: bool
    conversation_id: Optional[str] = None

    # UI Configuration
    title: str = "AI Chat"
    subtitle: Optional[str] = None
    placeholder_text: str = "Ask something..."
    empty_state_message: str = "Start talking to the AI"
    clear_button_text: str = "New chat"
    show_chat_code_block: bool = False

    @abstractmethod
    async def call_ai_chat(self, user_message: str) -> None:
        """Handle user message and call AI chat service.

        Args:
            user_message (str): The message from the user
        """

    @rx.var
    def messages_to_display(self) -> List[ChatMessage]:
        """Get the list of messages to display in the chat."""
        messages = self._chat_messages
        if not self.show_chat_code_block:
            messages = [msg for msg in messages if msg.type != "code"]
        return messages

    @rx.var
    def current_response_message(self) -> Optional[ChatMessage]:
        """Get the current response message being streamed."""
        current_messages = self._current_response_message
        if not self.show_chat_code_block and current_messages and current_messages.type == "code":
            return None
        return current_messages

    @rx.event(background=True)
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
            id=str(uuid.uuid4()),
            sources=[]
        )

        async with self:
            self._chat_messages.append(message)
            self.is_streaming = True

        try:
            await self.call_ai_chat(user_message)
        except Exception as e:
            Logger.log_exception_stack_trace(e)
            error_message = ChatMessageText(
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
            self._current_response_message = message

    async def update_current_message_sources(self, sources: List[RagChunk]) -> None:
        """Update the sources of the current streaming message"""
        async with self:
            if self._current_response_message:
                self._current_response_message.sources = sources

    async def close_current_message(self):
        """Close the current streaming message and add it to the chat history"""
        async with self:
            if self._current_response_message:
                self._chat_messages.append(self._current_response_message)
                self._current_response_message = None

    def set_conversation_id(self, conversation_id: str) -> None:
        self.conversation_id = conversation_id

    @rx.event
    def clear_chat(self) -> None:
        self._chat_messages = []
        self._current_response_message = None
        self.conversation_id = None

    # Helper methods to create different message types
    def create_text_message(
            self, content: str, role: str = "assistant", sources: Optional[List[RagChunk]] = None) -> ChatMessageText:
        """Create a text message"""
        return ChatMessageText(
            id=str(uuid.uuid4()),
            role=role,
            content=content,
            sources=sources or []
        )

    def create_code_message(
            self, content: str, role: str = "assistant", sources: Optional[List[RagChunk]] = None) -> ChatMessageCode:
        """Create a code message"""
        return ChatMessageCode(
            id=str(uuid.uuid4()),
            role=role,
            content=content,
            sources=sources or []
        )

    def create_image_message(self, data: Image.Image, content: str = "", role: str = "assistant",
                             sources: Optional[List[RagChunk]] = None) -> ChatMessageImage:
        """Create an image message"""
        return ChatMessageImage(
            id=str(uuid.uuid4()),
            role=role,
            content=content,
            data=data,
            sources=sources or []
        )

    def add_message(self, message: ChatMessage) -> None:
        """Add a message to the chat history"""
        self._chat_messages.append(message)

    @rx.event
    def open_ai_expert(self, rag_document_id: str):
        """Redirect the user to the AI Expert page."""
        return rx.redirect(f"/ai-expert/{rag_document_id}")

    @rx.event
    def open_document(self, rag_document_id: str):
        """Redirect the user to an external URL."""

        rag_resource = RagResource.from_document_id(rag_document_id)
        if not rag_resource:
            raise ValueError(f"Resource with ID {rag_document_id} not found")
        return self.open_document_from_resource(rag_resource.get_id())

    @rx.event
    def open_document_from_resource(self, resource_id: str):
        """Redirect the user to an external URL."""

        # Generate a public share link for the document
        generate_link_dto = GenerateShareLinkDTO.get_1_hour_validity(
            entity_id=resource_id,
            entity_type=ShareLinkEntityType.RESOURCE
        )

        with AuthenticateUser(self.get_and_check_current_user()):
            share_link = ShareLinkService.get_or_create_valid_public_share_link(generate_link_dto)

        if share_link:
            # Redirect the user to the share link URL
            return rx.redirect(share_link.get_public_link(), is_external=True)


@dataclass
class ChatConfig:
    """Simple configuration for chat component - only state is configurable"""

    # State configuration - this is the only customizable part
    state: Type[ChatStateBase]

    # Add custom button on top right of the header
    header_buttons: Callable[[], List[rx.Component]] | None = None

    sources_component: Callable[[List[RagChunk], ChatStateBase], rx.Component] | None = None
