import json
import os
import tempfile
import uuid
from abc import abstractmethod
from typing import List, Literal, Optional

import reflex as rx
from gws_core import (AuthenticateUser, GenerateShareLinkDTO,
                      ShareLinkEntityType, ShareLinkService)
from gws_core.core.utils.logger import Logger
from gws_reflex_main import ReflexMainState
from PIL import Image
from plotly.graph_objects import Figure

from gws_ai_toolkit.rag.common.rag_models import RagChatSource
from gws_ai_toolkit.rag.common.rag_resource import RagResource

from ..history.conversation_history_state import ConversationHistoryState
from .chat_message_class import (ChatMessage, ChatMessageCode,
                                 ChatMessageFront, ChatMessageImage,
                                 ChatMessageImageFront, ChatMessagePlotly,
                                 ChatMessagePlotlyFront, ChatMessageText)


class ChatStateBase(ReflexMainState, rx.State, mixin=True):
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
        _chat_messages (List[ChatMessage]): Complete message history
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
    _chat_messages: List[ChatMessage]
    _current_response_message: Optional[ChatMessage]
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

    @abstractmethod
    async def call_ai_chat(self, user_message: str) -> None:
        """Handle user message and call AI chat service.

        Args:
            user_message (str): The message from the user
        """

    @abstractmethod
    def _after_chat_cleared(self):
        """Hook called after chat is cleared to reset analysis-specific state"""

    @rx.var()
    async def messages_to_display(self) -> List[ChatMessageFront]:
        """Get the list of messages to display in the chat."""
        messages = self._chat_messages
        if not self.show_chat_code_block:
            messages = [msg for msg in messages if msg.type != "code"]

        image_folder = await self.get_images_folder_path()
        plot_folder = await self.get_plots_folder_path()
        messages = [self._convert_to_front_message_sync(msg, image_folder, plot_folder) for msg in messages]
        return [msg for msg in messages if msg is not None]  # type: ignore

    @rx.var
    async def current_response_message(self) -> Optional[ChatMessageFront]:
        """Get the current response message being streamed."""
        current_message = self._current_response_message

        if not current_message:
            return None
        if not self.show_chat_code_block and current_message and current_message.type == "code":
            return None

        image_folder = await self.get_images_folder_path()
        plot_folder = await self.get_plots_folder_path()
        return self._convert_to_front_message_sync(current_message, image_folder, plot_folder)

    def _convert_to_front_message_sync(
            self, message: ChatMessage, image_folder: str, plot_folder: str) -> ChatMessageFront | None:
        """Convert internal ChatMessage to front-end ChatMessageFront type."""
        if isinstance(message, ChatMessageImage):
            figure_path = os.path.join(image_folder, message.filename)
            return ChatMessageImageFront(
                id=message.id,
                role=message.role,
                sources=message.sources,
                image=Image.open(figure_path)  # Now using image_name as full path
            )
        if isinstance(message, ChatMessagePlotly):
            figure_path = os.path.join(plot_folder, message.filename)
            try:
                with open(figure_path, 'r', encoding='utf-8') as file:
                    figure_json = json.load(file)
            except Exception as e:
                Logger.log_exception_stack_trace(e)
                return None
            return ChatMessagePlotlyFront(
                id=message.id,
                role=message.role,
                sources=message.sources,
                figure=Figure(figure_json)
            )
        return message

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
        if not self.is_streaming:
            return
        async with self:
            self._current_response_message = message

    async def update_current_message_sources(self, sources: List[RagChatSource]) -> None:
        """Update the sources of the current streaming message"""
        if not self.is_streaming:
            return
        async with self:
            if self._current_response_message:
                self._current_response_message.sources = sources

    async def close_current_message(self):
        """Close the current streaming message and add it to the chat history"""
        if not self._current_response_message:
            return
        async with self:
            if self._current_response_message:
                self._chat_messages.append(self._current_response_message)
                self._current_response_message = None

    def set_external_conversation_id(self, external_conversation_id: str) -> None:
        self.external_conversation_id = external_conversation_id

    @rx.event
    def clear_chat(self) -> None:
        self._chat_messages = []
        self._current_response_message = None
        self._conversation_id = None
        self.external_conversation_id = None
        self.is_streaming = False
        self._after_chat_cleared()

    # Helper methods to create different message types
    def create_text_message(
            self,
            content: str,
            role: Literal['user', 'assistant'] = "assistant",
            external_id: Optional[str] = None,
            sources: Optional[List[RagChatSource]] = None) -> ChatMessageText:
        """Create a text message"""
        return ChatMessageText(
            id=str(uuid.uuid4()),
            role=role,
            content=content,
            external_id=external_id,
            sources=sources or []
        )

    def create_code_message(
            self,
            content: str,
            role: Literal['user', 'assistant'] = "assistant",
            external_id: Optional[str] = None,
            sources: Optional[List[RagChatSource]] = None) -> ChatMessageCode:
        """Create a code message"""
        return ChatMessageCode(
            id=str(uuid.uuid4()),
            role=role,
            code=content,
            external_id=external_id,
            sources=sources or []
        )

    async def create_image_message(self, image: Image.Image,
                                   role: Literal['user', 'assistant'] = "assistant",
                                   external_id: Optional[str] = None,
                                   sources: Optional[List[RagChatSource]] = None) -> ChatMessageImage:
        """Create an image message by saving the PIL Image to the history images folder"""
        history_state = await ConversationHistoryState.get_instance(self)
        filename = await history_state.save_image_to_history(image)

        return ChatMessageImage(
            id=str(uuid.uuid4()),
            role=role,
            filename=filename,  # Store the full path
            external_id=external_id,
            sources=sources or []
        )

    async def create_plotly_message(self,
                                    figure: Figure,
                                    role: Literal['user', 'assistant'] = "assistant",
                                    external_id: Optional[str] = None,
                                    sources: Optional[List[RagChatSource]] = None) -> ChatMessagePlotly:
        """Create a Plotly message with interactive figure"""
        history_state = await ConversationHistoryState.get_instance(self)
        filename = await history_state.save_plotly_figure_to_history(figure)
        return ChatMessagePlotly(
            id=str(uuid.uuid4()),
            role=role,
            filename=filename,
            external_id=external_id,
            sources=sources or []
        )

    def _save_image_to_temp(self, image: Image.Image) -> str:
        """Save PIL Image to temporary directory and return the file path"""
        # Create temp directory if it doesn't exist
        temp_dir = tempfile.gettempdir()
        chat_temp_dir = os.path.join(temp_dir, "chat_images")
        os.makedirs(chat_temp_dir, exist_ok=True)

        # Generate unique filename
        filename = f"image_{uuid.uuid4().hex}.png"
        file_path = os.path.join(chat_temp_dir, filename)

        # Save image
        image.save(file_path, format="PNG")

        return file_path

    def add_message(self, message: ChatMessage) -> None:
        """Add a message to the chat history"""
        if not self.is_streaming:
            return
        self._chat_messages.append(message)

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

        # Generate a public share link for the document
        generate_link_dto = GenerateShareLinkDTO.get_1_hour_validity(
            entity_id=resource_id,
            entity_type=ShareLinkEntityType.RESOURCE
        )

        with AuthenticateUser(await self.get_and_check_current_user()):
            share_link = ShareLinkService.get_or_create_valid_public_share_link(generate_link_dto)

        if share_link:
            public_link = share_link.get_public_link()
            if public_link:
                # Redirect the user to the share link URL
                return rx.redirect(public_link, is_external=True)

    async def save_conversation_to_history(self, mode: str, configuration: dict):
        """Save the current conversation to history with the given configuration."""
        if not self._chat_messages:
            return

        if self._conversation_id is None:
            async with self:
                self._conversation_id = str(uuid.uuid4())

        try:
            history_state: ConversationHistoryState
            async with self:
                history_state = await ConversationHistoryState.get_instance(self)
                await history_state.add_conversation(
                    conversation_id=self._conversation_id,
                    messages=self._chat_messages,
                    mode=mode,
                    configuration=configuration,
                    external_conversation_id=self.external_conversation_id
                )
        except Exception as e:
            Logger.error(f"Error saving conversation to history: {e}")
            Logger.log_exception_stack_trace(e)

    async def get_images_folder_path(self) -> str:
        """Get the folder path where chat images are stored."""
        history_state = await ConversationHistoryState.get_instance(self)
        return await history_state.get_images_folder_full_path()

    async def get_plots_folder_path(self) -> str:
        """Get the folder path where chat plots are stored."""
        history_state = await ConversationHistoryState.get_instance(self)
        return await history_state.get_plots_folder_full_path()
