import json
import os
from datetime import datetime
from typing import Any, Awaitable, Callable, Dict, List, Optional

import reflex as rx
from gws_core.core.utils.logger import Logger

from ..chat_base.chat_message_class import ChatMessage

from .conversation_history_class import (ConversationFullHistory,
                                         ConversationHistory)

# from gws_reflex_main import ReflexMainState


class ConversationHistoryState(rx.State):
    """State management for conversation history storage."""

    _history_file_path: str = ''

    _loader: Callable[['rx.State'], Awaitable[str]] = None

    @classmethod
    def set_loader(cls, loader: Callable[['ConversationHistoryState'], Awaitable[str]]) -> None:
        """Set the loader function to get the path of the history file."""
        cls._loader = loader

    # @classmethod
    # def set_loader_from_param(cls, param_name: str) -> None:
    #     """Set the loader function to get the history file path from a parameter."""
    #     async def loader(state: 'ConversationHistoryState') -> str:
    #         base_state = await state.get_state(ReflexMainState)
    #         return await base_state.get_param(param_name)

    #     cls._loader = loader

    @rx.var()
    async def history_file_path(self) -> str:
        """Get the history file path."""
        if not self._history_file_path:
            if not ConversationHistoryState._loader:
                # don't raise an error for the compilation
                return ''
                # raise ValueError("Loader function is not set. Please call ConversationHistoryState.set_loader")
            self._history_file_path = await ConversationHistoryState._loader(self) or ''

        return self._history_file_path

    async def _load_history(self) -> ConversationFullHistory:
        """Load conversation history from JSON file."""
        history_file_path = await self.history_file_path
        if history_file_path and os.path.exists(history_file_path):
            with open(history_file_path, 'r', encoding='utf-8') as file:
                try:
                    data = json.load(file)
                    return ConversationFullHistory.from_json(data)
                except json.JSONDecodeError as e:
                    Logger.log_exception_stack_trace(e)
                    return ConversationFullHistory(conversations=[])
        return ConversationFullHistory(conversations=[])

    async def _save_history(self, full_history: ConversationFullHistory) -> None:
        """Save conversation history to JSON file."""
        try:
            history_file_path = await self.history_file_path
            if not history_file_path:
                return

            # Ensure directory exists
            os.makedirs(os.path.dirname(history_file_path), exist_ok=True)

            # Convert ConversationFullHistory object to dict format for JSON serialization
            history_data = full_history.to_json_dict()

            with open(history_file_path, 'w', encoding='utf-8') as file:
                json.dump(history_data, file, indent=2, ensure_ascii=False)
        except Exception as e:
            Logger.log_exception_stack_trace(e)

    async def add_conversation(self,
                               conversation_id: str,
                               messages: List[ChatMessage],
                               mode: str,
                               configuration: Dict[str, Any]) -> None:
        """Add or update a conversation in the history.

        Args:
            conversation_id: Unique identifier for the conversation
            messages: List of chat messages in the conversation
            mode: Mode of the conversation (e.g., "RAG", "ai_expert")
            configuration: Configuration settings (mode, temperature, expert_mode, document_id, etc.)
        """
        try:
            full_history = await self._load_history()

            # Create new conversation object
            new_conversation = ConversationHistory(
                conversation_id=conversation_id,
                timestamp=datetime.now(),
                configuration=configuration,
                messages=messages,
                mode=mode,
                label=""  # Will be set automatically when messages are added
            )

            # Add conversation to full history (handles duplicates internally)
            full_history.add_conversation(new_conversation)

            # Keep only the last 100 conversations to prevent the file from growing too large
            # if len(full_history.conversations) > 100:
            #     full_history.conversations = full_history.conversations[-100:]

            await self._save_history(full_history)

        except Exception as e:
            Logger.log_exception_stack_trace(e)

    async def get_conversation_history(self, conversation_id: Optional[str] = None) -> ConversationFullHistory:
        """Get conversation history.

        Args:
            conversation_id: Optional specific conversation ID to retrieve

        Returns:
            ConversationFullHistory object containing all conversations or specific conversation if ID provided
        """
        try:
            full_history = await self._load_history()

            if conversation_id:
                specific_conversation = full_history.get_conversation_by_id(conversation_id)
                if specific_conversation:
                    return ConversationFullHistory(conversations=[specific_conversation])
                else:
                    return ConversationFullHistory(conversations=[])

            return full_history

        except Exception as e:
            Logger.log_exception_stack_trace(e)
            return ConversationFullHistory(conversations=[])

    async def clear_history(self) -> None:
        """Clear all conversation history."""
        try:
            empty_history = ConversationFullHistory(conversations=[])
            await self._save_history(empty_history)
        except Exception as e:
            Logger.log_exception_stack_trace(e)
