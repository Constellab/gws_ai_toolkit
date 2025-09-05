import json
import os
from abc import abstractmethod
from datetime import datetime
from typing import Any, Dict, List, Optional

import reflex as rx
from gws_core.core.utils.logger import Logger

from ..chat_base.chat_message_class import ChatMessage
from ..core.utils import Utils
from .conversation_history_class import (ConversationFullHistory,
                                         ConversationHistory)


class ConversationHistoryState(rx.State, mixin=True):
    """State management for conversation history storage."""

    _history_file_path: str = ''

    @abstractmethod
    async def _get_history_file_path_param(self) -> str:
        """Get the parameter name for history file path."""
        pass

    async def get_history_file_path(self) -> str:
        """Get the history file path."""
        if not self._history_file_path:
            self._history_file_path = await self._get_history_file_path_param()

        return self._history_file_path

    async def _load_history(self) -> ConversationFullHistory:
        """Load conversation history from JSON file."""
        history_file_path = await self.get_history_file_path()
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
            history_file_path = await self.get_history_file_path()
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

    @staticmethod
    async def get_instance(state: rx.State) -> 'ConversationHistoryState':
        """Get the ConversationHistoryState instance from any state."""

        config_state = await Utils.get_first_state_of_type(state, ConversationHistoryState)

        if config_state:
            return config_state
        else:
            raise ValueError(
                "ConversationHistoryState subclass not found. You must define a subclass of ConversationHistoryState in your app to configure it.")
