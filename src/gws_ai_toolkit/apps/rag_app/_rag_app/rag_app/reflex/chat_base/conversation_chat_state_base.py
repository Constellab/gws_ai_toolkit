from abc import abstractmethod
from typing import cast

import reflex as rx
from anyio import sleep
from gws_ai_toolkit.core.utils import Utils
from gws_ai_toolkit.models.chat.conversation.base_chat_conversation import BaseChatConversation
from gws_ai_toolkit.models.chat.message.chat_message_base import ChatMessageBase
from gws_ai_toolkit.models.chat.message.chat_message_streaming import ChatMessageStreaming
from gws_ai_toolkit.models.chat.message.chat_message_types import ChatMessageFront
from gws_ai_toolkit.models.chat.message.chat_user_message import (
    ChatUserMessageBase,
    ChatUserMessageText,
)
from gws_ai_toolkit.rag.common.rag_resource import RagResource
from gws_reflex_main import ReflexMainState


class ConversationChatStateBase(rx.State, mixin=True):
    """Abstract base class for chat state implementations using BaseChatConversation.

    This class provides the foundation for chat functionality that delegates
    message management to a BaseChatConversation object. The conversation object
    handles message storage, streaming state, and persistence.

    Key Features:
        - Delegates message management to BaseChatConversation
        - Streaming response handling with UI updates
        - Form submission and validation
        - Error handling and user feedback
        - Configurable UI properties

    State Attributes:
        All message state (chat_messages, current_response_message, is_streaming)
        is retrieved from the conversation object via computed properties.

    UI Configuration:
        title (str): Chat interface title
        subtitle (Optional[str]): Optional subtitle text
        placeholder_text (str): Input field placeholder
        empty_state_message (str): Message shown when chat is empty
        clear_button_text (str): Text for clear chat button
        show_chat_code_block (bool): Whether to display code blocks

    Abstract Methods:
        get_conversation(): Must be implemented to return the BaseChatConversation instance

    Usage:
        Subclass this to create specific chat implementations.
        Implement get_conversation() to provide the conversation object.
    """

    is_streaming: bool = False
    current_response_message: ChatMessageFront | None = None
    _chat_messages: list[ChatMessageBase] = []

    # UI Configuration
    title: str = "AI Chat"
    subtitle: str | None = None
    placeholder_text: str = "Ask something..."
    empty_state_message: str = "Start talking to the AI"
    clear_button_text: str = "New chat"
    show_chat_code_block: bool = False

    _conversation: BaseChatConversation | None = None

    @abstractmethod
    async def _create_conversation(self) -> BaseChatConversation:
        """Create the conversation object that manages messages and state.

        Returns:
            BaseChatConversation: The conversation instance
        """

    async def build_user_message(self, user_query: str) -> ChatUserMessageBase:
        """Hook to configure the conversation before processing a new message.

        Args:
            conversation (BaseChatConversation): The conversation instance
        """
        return ChatUserMessageText(content=user_query)

    async def _after_message_added(self, message: ChatMessageBase):
        """Hook called after a new message is added to the chat.

        Args:
            message (ChatMessageBase): The message that was just added
        """
        pass

    async def get_or_create_conversation(self) -> BaseChatConversation:
        """Get the conversation object that manages messages and state.

        Returns:
            BaseChatConversation: The conversation instance
        """
        if not self._conversation:
            conversation = await self._create_conversation()
            self._conversation = conversation
        return self._conversation

    @rx.event(background=True)  # type: ignore
    async def submit_input_form(self, form_data: dict) -> None:
        """On chat input form submit, check message and call AI chat

        Args:
            form_data (dict): The form data submitted by the user
        """
        user_message = form_data.get("message", "").strip()
        if not user_message:
            return

        if self.is_streaming:
            # Prevent multiple submissions while streaming
            return

        async with self:
            self.is_streaming = True

        async with self:
            conversation = await self.get_or_create_conversation()
            main_state = await self.get_state(ReflexMainState)

            with await main_state.authenticate_user():
                conversation.create_conversation(user_message)
                self._chat_messages = [msg.to_front_dto() for msg in conversation.chat_messages]

        await sleep(0.1)  # Allow UI to update before starting streaming

        user_query = await self.build_user_message(user_message)

        try:
            with await main_state.authenticate_user():
                # Call conversation and process the AI chat stream
                for message in conversation.call_conversation(user_query):
                    if isinstance(message, ChatMessageStreaming):
                        # Update current response message on each yield
                        async with self:
                            self.current_response_message = message
                    else:
                        # Add completed message to chat history
                        async with self:
                            self.current_response_message = None
                            self._chat_messages.append(message.to_front_dto())
                        await self._after_message_added(message)

        finally:
            # Clear current response message when finished
            async with self:
                self.current_response_message = None
                self.is_streaming = False

    @rx.event
    def clear_chat(self) -> None:
        """Clear the chat and reset the conversation."""
        self._conversation = None
        self._chat_messages = []
        self.current_response_message = None
        self.is_streaming = False

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
    def show_empty_chat(self) -> bool:
        """Check if there are no messages in the chat."""
        return (
            len(self._chat_messages) == 0
            and not self.current_response_message
            and not self.is_streaming
        )

    @rx.var
    def chat_messages(self) -> list[ChatMessageFront]:
        """Get all chat messages as DTOs for rendering."""
        return cast(list[ChatMessageFront], self._chat_messages)
