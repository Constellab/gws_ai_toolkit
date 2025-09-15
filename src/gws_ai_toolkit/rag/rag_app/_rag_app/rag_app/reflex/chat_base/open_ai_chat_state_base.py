import os
from abc import abstractmethod
from typing import Optional

import reflex as rx
from openai import OpenAI
from openai.types.responses import (ResponseCodeInterpreterCallCodeDeltaEvent,
                                    ResponseCreatedEvent,
                                    ResponseTextDeltaEvent)

from .chat_message_class import ChatMessage
from .chat_state_base import ChatStateBase


class OpenAiChatStateBase(ChatStateBase, rx.State, mixin=True):

    _previous_external_response_id: Optional[str] = None  # For conversation continuity
    _current_external_response_id: Optional[str] = None

    @abstractmethod
    async def call_ai_chat(self, user_message: str) -> None:
        """Handle user message and call AI chat service.

        Args:
            user_message (str): The message from the user
        """

    def _after_chat_cleared(self):
        """Hook called after chat is cleared to reset analysis-specific state"""
        self._previous_external_response_id = None
        self._current_external_response_id = None

    def _get_openai_client(self) -> OpenAI:
        """Get OpenAI client with API key"""
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise ValueError("OpenAI API key is not set")
        return OpenAI(api_key=api_key)

    async def handle_response_created(self, event: ResponseCreatedEvent):
        """Handle response.created event"""
        async with self:
            self._current_external_response_id = event.response.id

    async def handle_response_completed(self):
        """Handle response.completed event"""
        await self.close_current_message()
        async with self:
            self._previous_external_response_id = self._current_external_response_id
            self._current_external_response_id = None

    async def handle_output_text_delta(self, event: ResponseTextDeltaEvent):
        """Handle response.output_text.delta event"""
        text = event.delta

        current_message: Optional[ChatMessage] = None

        async with self:
            current_message = self._current_response_message

        if current_message and current_message.type == "text":
            async with self:
                current_message.content += text
        else:
            # Create new text message if none exists or if current is different type
            new_message = self.create_text_message(
                content=text,
                role="assistant",
                external_id=self._current_external_response_id

            )
            await self.update_current_response_message(new_message)

    async def handle_code_interpreter_call_code_delta(self, event: ResponseCodeInterpreterCallCodeDeltaEvent):
        """Handle response.code_interpreter_call_code.delta event"""
        code = event.delta

        current_message: Optional[ChatMessage] = None

        async with self:
            current_message = self._current_response_message

        if current_message and current_message.type == "code":
            async with self:
                current_message.code += code
        else:
            # Create new code message if none exists or if current is different type
            new_message = self.create_code_message(
                content=code,
                role="assistant",
                external_id=self._current_external_response_id
            )
            await self.update_current_response_message(new_message)
