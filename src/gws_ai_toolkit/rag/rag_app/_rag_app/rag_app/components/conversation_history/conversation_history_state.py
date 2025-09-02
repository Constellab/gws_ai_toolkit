import json
import os
from datetime import datetime
from typing import Any, Dict, List, Optional

import reflex as rx
from gws_core.core.utils.logger import Logger

from ..generic_chat.generic_chat_class import ChatMessage
from .conversation_history_class import (ConversationFullHistory,
                                         ConversationHistory)


class ConversationHistoryState(rx.State):
    """State management for conversation history storage."""

    HISTORY_FILE_PATH = "/lab/user/bricks/gws_ai_toolkit/src/gws_ai_toolkit/rag/rag_app/_rag_app/history.json"

    def _load_history(self) -> ConversationFullHistory:
        """Load conversation history from JSON file."""
        if os.path.exists(self.HISTORY_FILE_PATH):
            with open(self.HISTORY_FILE_PATH, 'r', encoding='utf-8') as file:
                try:
                    data = json.load(file)
                    return ConversationFullHistory.from_json(data)
                except json.JSONDecodeError as e:
                    Logger.log_exception_stack_trace(e)
                    return ConversationFullHistory(conversations=[])
        return ConversationFullHistory(conversations=[])

    def _save_history(self, full_history: ConversationFullHistory) -> None:
        """Save conversation history to JSON file."""
        try:
            # Ensure directory exists
            os.makedirs(os.path.dirname(self.HISTORY_FILE_PATH), exist_ok=True)

            # Convert ConversationFullHistory object to dict format for JSON serialization
            history_data = full_history.to_json_dict()

            with open(self.HISTORY_FILE_PATH, 'w', encoding='utf-8') as file:
                json.dump(history_data, file, indent=2, ensure_ascii=False)
        except Exception as e:
            Logger.log_exception_stack_trace(e)

    def add_conversation(self,
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
            full_history = self._load_history()

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

            self._save_history(full_history)

        except Exception as e:
            Logger.log_exception_stack_trace(e)

    def get_conversation_history(self, conversation_id: Optional[str] = None) -> ConversationFullHistory:
        """Get conversation history.

        Args:
            conversation_id: Optional specific conversation ID to retrieve

        Returns:
            ConversationFullHistory object containing all conversations or specific conversation if ID provided
        """
        try:
            full_history = self._load_history()

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

    def clear_history(self) -> None:
        """Clear all conversation history."""
        try:
            empty_history = ConversationFullHistory(conversations=[])
            self._save_history(empty_history)
        except Exception as e:
            Logger.log_exception_stack_trace(e)
