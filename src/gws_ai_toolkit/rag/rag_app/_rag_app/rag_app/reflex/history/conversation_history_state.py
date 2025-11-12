import json
import os
import uuid
from abc import abstractmethod
from datetime import datetime
from typing import Any, Dict, List, Optional, Type

import reflex as rx
from gws_core import Logger
from PIL import Image
from plotly.graph_objs import Figure

from ..chat_base.chat_message_class import ChatMessage
from .conversation_history_class import (ConversationFullHistory,
                                         ConversationHistory)


class ConversationHistoryState(rx.State, mixin=True):
    """State management for conversation history storage."""

    # Constants for folder and file structure
    HISTORY_FILE_NAME: str = 'history.json'
    IMAGES_FOLDER_NAME: str = 'images'
    PLOTS_FOLDER_NAME: str = 'plots'

    _history_folder_path: str = ''

    __sub_class_type__: Type['ConversationHistoryState'] | None = None

    @abstractmethod
    async def _get_history_folder_path_param(self) -> str:
        """Get the parameter name for history folder path."""
        pass

    async def get_history_folder_path(self) -> str:
        """Get the history folder path."""
        if not self._history_folder_path:
            self._history_folder_path = await self._get_history_folder_path_param()

        return self._history_folder_path

    async def get_history_file_path(self) -> str:
        """Get the full path to the history.json file."""
        folder_path = await self.get_history_folder_path()
        return os.path.join(folder_path, self.HISTORY_FILE_NAME)

    async def get_images_folder_full_path(self) -> str:
        """Get the full path to the images folder."""
        folder_path = await self.get_history_folder_path()
        return os.path.join(folder_path, self.IMAGES_FOLDER_NAME)

    async def get_plots_folder_full_path(self) -> str:
        """Get the full path to the plots folder."""
        folder_path = await self.get_history_folder_path()
        return os.path.join(folder_path, self.PLOTS_FOLDER_NAME)

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
            history_folder_path = await self.get_history_folder_path()
            if not history_folder_path:
                Logger.error("History folder path is not set.")
                return

            # Ensure folder structure exists
            os.makedirs(history_folder_path, exist_ok=True)
            images_folder_path = await self.get_images_folder_full_path()
            os.makedirs(images_folder_path, exist_ok=True)

            history_file_path = await self.get_history_file_path()

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
                               configuration: Dict[str, Any],
                               external_conversation_id: Optional[str] = None) -> None:
        """Add or update a conversation in the history.

        Args:
            conversation_id: Unique identifier for the conversation
            messages: List of chat messages in the conversation
            mode: Mode of the conversation (e.g., "RAG", "ai_expert")
            configuration: Configuration settings (mode, temperature, expert_mode, document_id, etc.)
            external_conversation_id: Optional ID from external system (openai, dify, ragflow...)
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
                label="",  # Will be set automatically when messages are added
                external_conversation_id=external_conversation_id
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

    async def save_image_to_history(self, image: Image.Image) -> str:
        """Save a PIL Image to the history images folder and return the filename.

        Args:
            image: PIL Image object to save

        Returns:
            str: The filename of the saved image (not the full path)
        """
        images_folder_path = await self.get_images_folder_full_path()
        os.makedirs(images_folder_path, exist_ok=True)

        # Generate unique filename
        filename = f"image_{uuid.uuid4().hex}.png"
        file_path = os.path.join(images_folder_path, filename)

        # Save image
        image.save(file_path, format="PNG")

        return filename

    async def save_plotly_figure_to_history(self, figure: Figure) -> str:
        """Save a Plotly Figure to the history images folder and return the filename.

        Args:
            figure: Plotly Figure object to save
        Returns:
            str: The filename of the saved plot (not the full path)
        """
        plots_folder_path = await self.get_plots_folder_full_path()
        os.makedirs(plots_folder_path, exist_ok=True)

        # Generate unique filename
        filename = f"plot_{uuid.uuid4().hex}.json"
        file_path = os.path.join(plots_folder_path, filename)

        # Save figure as JSON file
        figure.write_json(file_path)

        return filename

    @staticmethod
    async def get_instance(state: rx.State) -> 'ConversationHistoryState':
        """Get the ConversationHistoryState instance from any state."""

        if ConversationHistoryState.__sub_class_type__ is None:
            raise Exception(
                "ConversationHistoryState subclass not registered. You must call "
                "set_conversation_history_state_class_type() during app initialization to register "
                "your custom ConversationHistoryState subclass."
            )

        return await state.get_state(ConversationHistoryState.__sub_class_type__)

    @staticmethod
    def set_conversation_history_state_class_type(state_type: Type['ConversationHistoryState']):
        """Set the ConversationHistoryState subclass type for the app.

        Args:
            state_type (Type[ConversationHistoryState]): The ConversationHistoryState subclass type.
        """

        if ConversationHistoryState.__sub_class_type__ is not None:
            raise ValueError(
                "ConversationHistoryState subclass type is already set. Use Utils.get_first_state_of_type to get the instance.")

        ConversationHistoryState.__sub_class_type__ = state_type
