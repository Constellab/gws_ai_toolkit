

import os
from typing import List

import plotly.io as pio
from gws_ai_toolkit.core.ai_toolkit_db_manager import AiToolkitDbManager
from gws_ai_toolkit.models.chat import chat_app
from gws_ai_toolkit.models.chat.chat_app import ChatApp
from gws_ai_toolkit.models.chat.chat_app_service import ChatAppService
from gws_ai_toolkit.models.chat.chat_conversation import ChatConversation
from gws_ai_toolkit.models.chat.chat_conversation_dto import (
    SaveChatConversationDTO, SaveChatMessageSourceDTO)
from gws_ai_toolkit.models.chat.chat_message import \
    ChatMessage as ChatMessageModel
from gws_ai_toolkit.models.chat.chat_message_dto import (ChatMessageCode,
                                                         ChatMessageDTO,
                                                         ChatMessageError,
                                                         ChatMessageHint,
                                                         ChatMessageImage,
                                                         ChatMessagePlotly,
                                                         ChatMessageText)
from gws_ai_toolkit.models.chat.chat_message_source import ChatMessageSource
from gws_core import BrickService
from PIL import Image
from plotly.graph_objects import Figure


class ChatConversationService:
    """Service class for managing chat conversations, messages, and sources.

    Provides methods to create, retrieve, and manage ChatConversation, ChatMessage,
    and ChatMessageSource instances.
    """

    HISTORY_EXTENSION_FOLDER_NAME = "chat_conversations"

    def get_conversations_by_chat_app(
        self,
        chat_app_name: str
    ) -> List[ChatConversation]:
        """Get all conversations for a chat app.

        :param chat_app_name: The name of the chat app
        :type chat_app_name: str
        :return: List of conversations
        :rtype: List[ChatConversation]
        """
        chat_app = ChatAppService().get_by_name(chat_app_name)
        if not chat_app:
            return []
        return list(ChatConversation.get_by_chat_app(chat_app.id))

    @AiToolkitDbManager.transaction()
    def save_conversation(self, conversation_dto: SaveChatConversationDTO) -> ChatConversation:
        """Create a conversation with optional messages.

        :param conversation_dto: The conversation data including messages
        :type conversation_dto: SaveChatConversationDTO
        :return: The created conversation
        :rtype: ChatConversation
        """
        # Verify chat app exists
        chat_app = ChatAppService().get_or_create(conversation_dto.chat_app_name)

        if conversation_dto.id:
            conversation = ChatConversation.get_by_id_and_check(conversation_dto.id)
        else:
            # Create conversation
            conversation = ChatConversation()
        conversation.chat_app = chat_app
        conversation.configuration = conversation_dto.configuration
        conversation.mode = conversation_dto.mode
        conversation.label = conversation_dto.label or ""
        conversation.external_conversation_id = conversation_dto.external_conversation_id
        conversation.save()

        # Create messages if provided
        if conversation_dto.messages:
            for message_dto in conversation_dto.messages:
                self._save_message(conversation, message_dto)

        return conversation

    def _save_message(self, conversation: ChatConversation, message_dto: ChatMessageDTO) -> ChatMessageDTO:
        """Create a message in a conversation with optional sources.

        :param conversation_id: The ID of the conversation
        :type conversation_id: str
        :param message_dto: The message data including optional sources
        :type message_dto: ChatMessageDTO
        :return: The created message as a ChatMessage union type
        :rtype: ChatMessage
        """

        if message_dto.id:
            return message_dto

        # Verify conversation exists
        conversation_folder_path = self.get_conversation_folder_path(conversation.id)

        # Create message for other types
        message = ChatMessageModel()
        message.conversation = conversation
        message.role = message_dto.role
        message.type = message_dto.type
        message.external_id = message_dto.external_id

        # Handle front-end types that need conversion
        if isinstance(message_dto, ChatMessageImage) and message_dto.image:
            message.filename = self._save_image_to_folder(message.id, message_dto.image, conversation_folder_path)
        elif isinstance(message_dto, ChatMessagePlotly) and message_dto.figure:
            message.filename = self._save_plotly_figure_to_folder(
                message.id, message_dto.figure, conversation_folder_path)

        # Handle content based on message type
        if isinstance(message_dto, (ChatMessageText, ChatMessageHint)):
            message.message = message_dto.content
        elif isinstance(message_dto, ChatMessageError):
            message.message = message_dto.error
        else:
            message.message = ''

        # Handle data based on message type
        if isinstance(message_dto, ChatMessageCode):
            message.data = {'code': message_dto.code}
        else:
            message.data = {}

        message.save()

        # Create sources if provided
        if message_dto.sources:
            self._create_sources_for_message(message, message_dto.sources)

        return message.to_chat_message(conversation_folder_path)

    def get_messages_of_conversation(self, conversation_id: str) -> List[ChatMessageDTO]:
        """Get all messages of a conversation with their sources loaded.

        :param conversation_id: The ID of the conversation
        :type conversation_id: str
        :return: List of ChatMessage union type instances with sources
        :rtype: List[ChatMessage]
        """
        # Verify conversation exists
        ChatConversation.get_by_id_and_check(conversation_id)

        # Get messages ordered by creation date
        messages = ChatMessageModel.get_by_conversation(conversation_id)

        conversation_folder_path = self.get_conversation_folder_path(conversation_id)

        return [message.to_chat_message(conversation_folder_path) for message in messages]

    def get_conversation_folder_path(self, conversation_id: str) -> str:
        """Get the folder path for storing conversation files.

        :param conversation_id: The ID of the conversation
        :type conversation_id: str
        :return: The folder path for the conversation
        :rtype: str
        """
        return BrickService.get_brick_extension_dir(
            'gws_ai_toolkit',
            os.path.join(self.HISTORY_EXTENSION_FOLDER_NAME, conversation_id)
        )

    @AiToolkitDbManager.transaction()
    def delete_conversation(self, conversation_id: str) -> None:
        """Delete a conversation and all its messages and sources (CASCADE).

        :param conversation_id: The ID of the conversation to delete
        :type conversation_id: str
        :raises NotFoundException: If the conversation is not found
        """
        conversation = ChatConversation.get_by_id_and_check(conversation_id)
        conversation.delete_instance()

    def _create_sources_for_message(
            self,
            message: ChatMessageModel,
            sources: List[SaveChatMessageSourceDTO] | None) -> List[ChatMessageSource]:
        """Create source records for a message.

        :param message: The message to attach sources to
        :type message: ChatMessageModel
        :param sources: List of SaveChatMessageSourceDTO
        :type sources: List[SaveChatMessageSourceDTO]
        """

        if not sources:
            return []

        db_sources: List[ChatMessageSource] = []

        for source in sources:
            source_record = ChatMessageSource()
            source_record.message = message  # type: ignore
            source_record.document_id = source.document_id
            source_record.document_name = source.document_name
            source_record.score = source.score
            source_record.set_chunks(source.chunks)

            db_sources.append(source_record.save())
        return db_sources

    def _save_image_to_folder(self, id_: str, image: Image.Image, folder_path: str) -> str:
        """Save PIL Image to conversation folder and return the filename.

        :param image: The PIL Image to save
        :type image: Image.Image
        :param folder_path: The folder path to save the image in
        :type folder_path: str
        :return: The filename of the saved image
        :rtype: str
        """

        # Ensure folder exists
        os.makedirs(folder_path, exist_ok=True)

        # Generate unique filename
        filename = f"image_{id_}.png"
        file_path = os.path.join(folder_path, filename)

        # Save image
        image.save(file_path, format="PNG")

        return filename

    def _save_plotly_figure_to_folder(self, id_: str, figure: Figure, folder_path: str) -> str:
        """Save Plotly figure to conversation folder and return the filename.

        :param figure: The Plotly Figure to save
        :type figure: Figure
        :param folder_path: The folder path to save the figure in
        :type folder_path: str
        :return: The filename of the saved figure
        :rtype: str
        """

        # Ensure folder exists
        os.makedirs(folder_path, exist_ok=True)

        # Generate unique filename
        filename = f"plot_{id_}.json"
        file_path = os.path.join(folder_path, filename)

        # Save figure as JSON
        pio.write_json(figure, file_path)

        return filename
