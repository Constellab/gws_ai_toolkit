

import os
from typing import TYPE_CHECKING, List, Literal

import plotly.graph_objects as go
import plotly.io as pio
from gws_ai_toolkit.core.ai_toolkit_db_manager import AiToolkitDbManager
from gws_ai_toolkit.models.chat.chat_conversation import ChatConversation
from gws_ai_toolkit.models.chat.chat_message_dto import (ChatMessageCode,
                                                         ChatMessageDTO,
                                                         ChatMessageError,
                                                         ChatMessageHint,
                                                         ChatMessageImage,
                                                         ChatMessagePlotly,
                                                         ChatMessageText)
from gws_core import Model
from peewee import CharField, ForeignKeyField
from PIL import Image

if TYPE_CHECKING:
    from gws_ai_toolkit.models.chat.chat_message_source import \
        ChatMessageSource


class ChatMessage(Model):
    """Model representing a chat message.

    Based on ChatMessageBase class attributes:
        conversation: Foreign key to ChatConversation
        role: Role of the message sender (user or assistant)
        type: Type of message (text, image, code, plotly, error, hint)
        external_id: Optional external system ID for the message
        content: Content of the message (stored as string)
        data: Additional data object stored as JSON
    """

    conversation: ChatConversation = ForeignKeyField(
        ChatConversation, backref='+', on_delete='CASCADE')
    role: Literal['user', 'assistant'] = CharField()
    type: Literal["text", "image", "code", "plotly", "error", "hint"] = CharField()
    external_id: str | None = CharField(null=True)
    message: str = CharField()
    filename: str | None = CharField(null=True)
    data: dict = CharField(null=True)

    sources: List['ChatMessageSource']

    class Meta:
        table_name = 'gws_ai_toolkit_chat_message'
        database = AiToolkitDbManager.get_instance().db
        is_table = True
        db_manager = AiToolkitDbManager.get_instance()

    @classmethod
    def get_by_conversation(cls, conversation_id: str) -> List['ChatMessage']:
        """Get messages by conversation ID, ordered by creation date (oldest first).

        :param conversation_id: The ID of the conversation
        :type conversation_id: str
        :return: ModelSelect query for messages
        :rtype: List[ChatMessage]
        """
        return list(cls
                    .select()
                    .where(cls.conversation == conversation_id)
                    .order_by(cls.created_at.asc()))

    @classmethod
    def create_message(cls, conversation: ChatConversation, role: str, type_: str,
                       content: str, external_id: str | None = None, data: dict | None = None,
                       filename: str | None = None) -> 'ChatMessage':
        message = cls()
        message.conversation = conversation
        message.role = role
        message.type = type_
        message.message = content
        message.external_id = external_id
        message.data = data or {}
        message.filename = filename
        message.save()
        return message

    def to_chat_message(self, conversation_folder_path: str) -> ChatMessageDTO:
        """Convert database ChatMessage model to RAG app ChatMessage union type.

        :return: ChatMessage union type instance (from RAG app)
        :rtype: RagChatMessage
        """

        # Convert sources from ChatMessageSourceDTO to RagChatSource format
        sources = [source.to_rag_dto() for source in self.sources]

        # Common parameters for all message types
        common_params = {
            'id': self.id,
            'role': self.role,
            'external_id': self.external_id,
            'sources': sources
        }

        # Create the appropriate message type based on the type field
        if self.type == 'text':
            return ChatMessageText(
                **common_params,
                content=self.message
            )
        elif self.type == 'image':
            image: Image.Image | None = None

            file_path = self._get_filepath_if_exists(conversation_folder_path)
            if file_path:
                # Load image from file
                try:
                    image = Image.open(file_path)
                except Exception:
                    pass
            return ChatMessageImage(
                **common_params,
                image=image
            )
        elif self.type == 'code':
            return ChatMessageCode(
                **common_params,
                code=self.data.get('code', '')
            )
        elif self.type == 'plotly':
            figure: go.Figure | None = None

            file_path = self._get_filepath_if_exists(conversation_folder_path)

            if file_path:

                # Load figure from file
                try:
                    figure = pio.read_json(file_path)
                except Exception:
                    figure = None

            return ChatMessagePlotly(
                **common_params,
                figure=figure
            )
        elif self.type == 'error':
            return ChatMessageError(
                **common_params,
                error=self.message
            )
        elif self.type == 'hint':
            return ChatMessageHint(
                **common_params,
                content=self.message
            )
        else:
            # Default to text message if type is unknown
            return ChatMessageText(
                **common_params,
                content=self.message
            )

    def _get_filepath_if_exists(self, conversation_folder_path: str) -> str | None:
        """Get the full file path for the message's filename if it exists.

        :param conversation_folder_path: The folder path of the conversation
        :type conversation_folder_path: str
        :return: Full file path if exists, else None
        :rtype: str | None
        """
        if self.filename:
            file_path = os.path.join(conversation_folder_path, self.filename)
            if os.path.exists(file_path):
                return file_path
        return None
