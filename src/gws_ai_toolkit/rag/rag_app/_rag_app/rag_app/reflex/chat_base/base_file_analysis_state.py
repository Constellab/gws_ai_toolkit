import io
import os
from abc import abstractmethod
from typing import Optional, Union, cast

import reflex as rx
from gws_core import BaseModelDTO, File, Logger, ResourceModel
from openai import OpenAI
from PIL import Image

from .chat_message_class import ChatMessage, ChatMessageImage, ChatMessageText
from .chat_state_base import ChatStateBase


class BaseFileAnalysisState(ChatStateBase):
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

    # File context
    current_file_id: str = ""
    openai_file_id: Optional[str] = None
    _current_resource_model: Optional[ResourceModel] = None

    @abstractmethod
    def validate_resource(self, resource: ResourceModel) -> bool:
        """Validate if file is compatible with this analysis type

        Args:
            resource (ResourceModel): Resource model to validate

        Returns:
            bool: True if file is compatible, False otherwise
        """
        pass

    @abstractmethod
    async def get_config(self) -> BaseModelDTO:
        """Get configuration for this analysis type

            Returns:
                Configuration object specific to the analysis type
            """
        pass

    @abstractmethod
    def get_analysis_type(self) -> str:
        """Return analysis type for history saving

        Returns:
            str: Analysis type identifier (e.g., 'ai_expert', 'ai_table')
        """
        pass

    @abstractmethod
    def _load_resource_from_id(self, resource_id: str) -> ResourceModel:
        """Load the resource model from DataHub by ID

        Args:
            resource_id (str): ID of the resource to load

        Returns:
            Optional[ResourceModel]: Loaded resource model or None if not found
        """
        pass

    @abstractmethod
    async def call_ai_chat(self, user_message: str):
        """Get streaming response from OpenAI about the file

        Args:
            user_message (str): User's message to send to OpenAI
        """
        pass

    async def load_resource_from_url(self):
        """Handle page load - get resource ID from router state"""
        # Get the dynamic route parameter - different subclasses may use different parameter names
        resource_id = self.object_id if hasattr(self, 'object_id') else None

        if self.current_file_id and self.current_file_id != resource_id:
            # Reset chat if loading a different file
            self.clear_chat()

        if resource_id and str(resource_id).strip():
            await self.load_resource(str(resource_id))

    def _get_openai_client(self) -> OpenAI:
        """Get OpenAI client with API key"""
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise ValueError("OpenAI API key is not set")
        return OpenAI(api_key=api_key)

    async def load_resource(self, resource_id: str):
        """Load the file resource from DataHub and prepare for chat"""
        self.current_file_id = resource_id

        # Load the resource model directly
        resource_model = self._load_resource_from_id(resource_id)

        self._current_resource_model = resource_model
        self.subtitle = resource_model.name

    async def handle_output_text_delta(self, event):
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
                role="assistant"
            )
            await self.update_current_response_message(new_message)

    async def handle_code_interpreter_call_code_delta(self, event):
        """Handle response.code_interpreter_call_code.delta event"""
        code = event.delta

        current_message: Optional[ChatMessage] = None

        async with self:
            current_message = self._current_response_message

        if current_message and current_message.type == "code":
            async with self:
                current_message.content += code
        else:
            # Create new code message if none exists or if current is different type
            new_message = self.create_code_message(
                content=code,
                role="assistant"
            )
            await self.update_current_response_message(new_message)

    async def handle_output_text_annotation_added(self, event):
        """Handle response.output_text_annotation.added event"""
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
                    role="assistant"
                )
                await self.update_current_response_message(error_message)
            except Exception as e:
                Logger.log_exception_stack_trace(e)
                # Create error message for unexpected errors
                error_message = self.create_text_message(
                    content=f"[Unexpected error loading image: {str(e)}]",
                    role="assistant"
                )
                await self.update_current_response_message(error_message)

    async def upload_file_to_openai(self) -> str:
        """Upload the file to OpenAI and return file ID"""
        if self.openai_file_id:
            return self.openai_file_id

        if not self._current_resource_model:
            raise ValueError("No resource loaded")

        client = self._get_openai_client()

        file = cast(File, self._current_resource_model.get_resource())

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
                return self.create_image_message(
                    data=image_data,
                    content="",  # No text content for pure images
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
        if self._current_resource_model:
            return await self.open_document_from_resource(self._current_resource_model.id)
        return None

    async def close_current_message(self):
        """Close the current streaming message and add it to the chat history, then save to conversation history."""
        await super().close_current_message()
        # Save conversation after message is added to history
        await self._save_conversation_to_history()

    async def _save_conversation_to_history(self):
        """Save current conversation to history with analysis-specific configuration."""
        config: BaseModelDTO
        async with self:
            config = await self.get_config()

        # Build configuration dictionary with analysis-specific settings
        configuration = {
            "analysis_type": self.get_analysis_type(),
            "resource_id": self._current_resource_model.id,
            "file_name": self._current_resource_model.name,
            "config": config.to_json_dict()
        }

        # Save conversation to history after response is completed
        await self.save_conversation_to_history(self.get_analysis_type(), configuration)

    def get_current_resource_model(self) -> Optional[ResourceModel]:
        """Get the currently loaded resource model."""
        return self._current_resource_model
