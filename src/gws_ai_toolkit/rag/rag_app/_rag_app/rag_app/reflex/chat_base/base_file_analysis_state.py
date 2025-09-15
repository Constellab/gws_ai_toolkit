import io
import os
from abc import abstractmethod
from typing import Optional, Union, cast

import reflex as rx
from gws_core import BaseModelDTO, File, Logger, ResourceModel
from openai import OpenAI
from openai.types.responses import ResponseOutputTextAnnotationAddedEvent
from PIL import Image

from ..chat_base.open_ai_chat_state_base import OpenAiChatStateBase
from .chat_message_class import ChatMessageImage, ChatMessageText


class BaseFileAnalysisState(OpenAiChatStateBase, rx.State, mixin=True):
    """Abstract base class for file-based AI analysis (documents, tables, etc.)

    This class provides the foundation for all file analysis functionality,
    defining the common interface, state management, and core methods that all
    file analysis implementations must provide. It handles file loading, OpenAI
    integration, streaming responses, and conversation persistence.

    Key Features:
        - Abstract interface for AI file analysis integration
        - File loading and validation
        - OpenAI integration with streaming responses
        - File upload to OpenAI with code interpreter access
        - Conversation history integration
        - Error handling and user feedback

    State Attributes:
        current_file_id (str): ID of the currently loaded file
        openai_file_id (Optional[str]): OpenAI file ID when file is uploaded
        _current_resource_model (Optional[ResourceModel]): Loaded file resource

    Abstract Methods:
        validate_file(file_path): Must validate if file is compatible with analysis type
        get_config(): Must return configuration for this analysis type
        get_analysis_type(): Must return analysis type string for history saving

    Usage:
        Subclass this to create specific analysis implementations like AI Expert or AI Table.
        Implement the abstract methods to provide type-specific behavior.
    """

    openai_file_id: Optional[str] = None
    _current_resource_model: Optional[ResourceModel] = None

    _previous_external_response_id: Optional[str] = None  # For conversation continuity
    _current_external_response_id: Optional[str] = None

    @abstractmethod
    def validate_resource(self, resource: ResourceModel) -> bool:
        """Validate if file is compatible with this analysis type

        Args:
            resource (ResourceModel): Resource model to validate

        Returns:
            bool: True if file is compatible, False otherwise
        """

    @abstractmethod
    async def get_config(self) -> BaseModelDTO:
        """Get configuration for this analysis type

            Returns:
                Configuration object specific to the analysis type
            """

    @abstractmethod
    def get_analysis_type(self) -> str:
        """Return analysis type for history saving

        Returns:
            str: Analysis type identifier (e.g., 'ai_expert', 'ai_table')
        """

    @abstractmethod
    def _load_resource(self) -> Optional[ResourceModel]:
        """Load the resource model from DataHub by ID

        Returns:
            Optional[ResourceModel]: Loaded resource model or None if not found
        """

    @abstractmethod
    async def call_ai_chat(self, user_message: str):
        """Get streaming response from OpenAI about the file

        Args:
            user_message (str): User's message to send to OpenAI
        """

    async def handle_output_text_annotation_added(self, event: ResponseOutputTextAnnotationAddedEvent):
        """Handle response.output_text.annotation.added event"""
        annotation = event.annotation

        # Extract file from annotation
        if isinstance(annotation, dict) and 'file_id' in annotation and 'filename' in annotation:
            try:
                client = self._get_openai_client()
                file_message = await self.extract_file_from_response(
                    annotation['file_id'], annotation['filename'], client,
                    container_id=annotation.get('container_id'))
                await self.update_current_response_message(file_message)

            except (OSError, ValueError) as e:
                Logger.log_exception_stack_trace(e)
                # Create error message if image loading fails
                error_message = self.create_text_message(
                    content=f"[Error loading image: {str(e)}]",
                    role="assistant",
                    external_id=self._current_external_response_id
                )
                await self.update_current_response_message(error_message)
            except Exception as e:
                Logger.log_exception_stack_trace(e)
                # Create error message for unexpected errors
                error_message = self.create_text_message(
                    content=f"[Unexpected error loading image: {str(e)}]",
                    role="assistant",
                    external_id=self._current_external_response_id
                )
                await self.update_current_response_message(error_message)

    async def upload_file_to_openai(self) -> str:
        """Upload the file to OpenAI and return file ID"""
        if self.openai_file_id:
            return self.openai_file_id

        resource_model = await self.get_current_resource_model()
        if not resource_model:
            raise ValueError("No resource loaded")

        client = self._get_openai_client()

        file = cast(File, resource_model.get_resource())

        # Upload file to OpenAI
        with open(file.path, "rb") as f:
            uploaded_file = client.files.create(
                file=f,
                purpose="assistants"
            )

        async with self:
            self.openai_file_id = uploaded_file.id

        return uploaded_file.id

    async def extract_file_from_response(self, file_id: str, filename: str, client: OpenAI,
                                         container_id: Optional[str] = None) -> Union[ChatMessageImage, ChatMessageText]:
        """Extract file from OpenAI response - handles images and other files"""

        file_data_binary = None

        try:
            if file_id.startswith('cfile_') and container_id:
                # Container file - use containers API
                file_data_binary = client.containers.files.content.retrieve(file_id, container_id=container_id)
            else:
                # Regular file - use files API
                file_data_binary = client.files.content(file_id)

            # Check file extension to determine handling
            file_extension = os.path.splitext(filename)[1].lower()

            # Handle image files
            if file_extension in ['.png', '.jpg', '.jpeg', '.gif', '.bmp', '.webp']:
                image_data = Image.open(io.BytesIO(file_data_binary.content))

                async with self:
                    return await self.create_image_message(
                        image=image_data,
                        role="assistant"
                    )
            else:
                # Handle other file types as text messages
                return self.create_text_message(
                    content=f"📄 File '{filename}' has been generated.",
                    role="assistant"
                )

        except Exception as e:
            Logger.log_exception_stack_trace(e)
            raise ValueError(f"Error downloading file {file_id}: {str(e)}")

    @rx.event
    async def open_current_resource_file(self):
        """Open the current resource file."""
        resource_model = await self.get_current_resource_model()
        if resource_model:
            return await self.open_document_from_resource(resource_model.id)
        return None

    async def close_current_message(self):
        """Close the current streaming message and add it to the chat history, then save to conversation history."""
        if not self._current_response_message:
            return
        await super().close_current_message()
        # Save conversation after message is added to history
        await self._save_conversation_to_history()

    async def _save_conversation_to_history(self):
        """Save current conversation to history with analysis-specific configuration."""
        config: BaseModelDTO
        async with self:
            config = await self.get_config()

        resource = await self.get_current_resource_model()

        # Build configuration dictionary with analysis-specific settings
        configuration = {
            "analysis_type": self.get_analysis_type(),
            "resource_id": resource.id,
            "file_name": resource.name,
            "config": config.to_json_dict()
        }

        # Save conversation to history after response is completed
        await self.save_conversation_to_history(self.get_analysis_type(), configuration)

    async def get_current_resource_model(self) -> Optional[ResourceModel]:
        """Get the currently loaded resource model."""
        if not self._current_resource_model:
            self._current_resource_model = await self._load_resource_from_url()

        return self._current_resource_model

    async def _load_resource_from_url(self) -> Optional[ResourceModel]:
        """Handle page load - get resource ID from router state"""

        resource_model = self._load_resource()

        if not resource_model:
            self.clear_chat()
            return None

        if self._current_resource_model and self._current_resource_model.id != resource_model.id:
            # Reset chat if loading a different file
            self.clear_chat()

        self.subtitle = resource_model.name
        return resource_model
