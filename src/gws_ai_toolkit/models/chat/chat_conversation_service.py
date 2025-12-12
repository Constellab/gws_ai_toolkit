from gws_core import CurrentUserService, PageDTO, Paginator

from gws_ai_toolkit.core.ai_toolkit_db_manager import AiToolkitDbManager
from gws_ai_toolkit.models.chat.chat_app_service import ChatAppService
from gws_ai_toolkit.models.chat.chat_conversation import ChatConversation
from gws_ai_toolkit.models.chat.chat_conversation_dto import SaveChatConversationDTO
from gws_ai_toolkit.models.chat.chat_message_model import ChatMessageModel
from gws_ai_toolkit.models.chat.chat_message_source_model import ChatMessageSourceModel
from gws_ai_toolkit.models.chat.message.chat_message_base import ChatMessageBase
from gws_ai_toolkit.models.chat.message.chat_message_source import ChatMessageSource
from gws_ai_toolkit.models.user.user import User
from gws_ai_toolkit.rag.common.rag_models import RagChatSource


class ChatConversationService:
    """Service class for managing chat conversations, messages, and sources.

    Provides methods to create, retrieve, and manage ChatConversation, ChatMessage,
    and ChatMessageSource instances.
    """

    HISTORY_EXTENSION_FOLDER_NAME = "chat_conversations"

    def get_my_conversations_by_chat_app(self, chat_app_name: str) -> list[ChatConversation]:
        """Get all conversations for a chat app.

        :param chat_app_name: The name of the chat app
        :type chat_app_name: str
        :return: List of conversations
        :rtype: List[ChatConversation]
        """
        chat_app = ChatAppService().get_by_name(chat_app_name)
        if not chat_app:
            return []
        return list(
            ChatConversation.get_by_chat_app_and_user(chat_app.id, self._get_current_user().id)
        )

    def get_message_sources_by_chat_app(
        self, chat_app_name: str, page: int = 0, number_of_items_per_page: int = 20
    ) -> PageDTO[RagChatSource]:
        """Get all message sources for a specific chat app by performing joins.

        This method joins ChatMessageSourceModel -> ChatMessageModel -> ChatConversation
        and filters by chat_app_id. Returns distinct sources by document_id.

        :param chat_app_name: The name of the chat app
        :type chat_app_name: str
        :return: List of chat message sources distinct by document_id, ordered by creation date (most recent first)
        :rtype: list[ChatMessageSourceModel]
        """
        # Get the chat app first and check if it exists
        chat_app = ChatAppService().get_by_name(chat_app_name)
        if not chat_app:
            return PageDTO.empty_page()

        current_user = self._get_current_user()

        paginator = Paginator(
            ChatMessageSourceModel.select()
            .join(ChatMessageModel)
            .join(ChatConversation)
            .where(
                (ChatConversation.chat_app == chat_app.id)
                & (ChatConversation.user == current_user.id)
            )
            .group_by(ChatMessageSourceModel.document_id)
            .order_by(ChatMessageSourceModel.created_at.desc()),
            page=page,
            nb_of_items_per_page=number_of_items_per_page,
        )

        return paginator.to_dto()

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
        conversation.label = conversation_dto.label or "New Conversation"
        conversation.external_conversation_id = conversation_dto.external_conversation_id
        conversation.user = self._get_current_user()
        conversation.save()

        # Create messages if provided
        if conversation_dto.messages:
            for message_dto in conversation_dto.messages:
                self._save_message(conversation, message_dto)

        return conversation

    def _save_message(
        self, conversation: ChatConversation, message: ChatMessageBase
    ) -> ChatMessageBase:
        """Internal method to save a message with its sources.

        Used by save_conversation when creating conversations with messages.

        :param conversation: The conversation to save the message to
        :type conversation: ChatConversation
        :param message: The message DTO to save
        :type message: ChatMessageBase
        :return: The saved message as DTO
        :rtype: ChatMessageBase
        """
        # Skip if message already has an ID (already saved)
        if message.id:
            return message

        # Convert DTO to model and save
        message_model = message.to_chat_message_model(conversation)
        message_model.user = self._get_current_user()
        message_model.save()

        # Create sources if provided (sources should be RagChatSource from the DTO)
        if isinstance(message, ChatMessageSource) and message.sources:
            self._create_sources_for_message(message_model, message.sources)

        return message_model.to_chat_message()

    @AiToolkitDbManager.transaction()
    def save_message(
        self,
        conversation_id: str,
        message: ChatMessageBase,
    ) -> ChatMessageBase:
        """Save a message of any type to a conversation.

        This method uses polymorphism - each message DTO knows how to convert itself
        to a database model. This is the main entry point for saving messages.

        :param conversation_id: The ID of the conversation
        :type conversation_id: str
        :param message_dto: The message DTO (any subclass of ChatMessageBase)
        :type message_dto: ChatMessageBase
        :return: The saved message as DTO
        :rtype: ChatMessageBase
        """
        conversation = ChatConversation.get_by_id_and_check(conversation_id)

        # Convert DTO to database model (polymorphic - each subclass handles itself)
        message_model = message.to_chat_message_model(conversation)
        message_model.user = self._get_current_user()
        message_model.save()

        # Create sources if provided
        if isinstance(message, ChatMessageSource) and message.sources:
            self._create_sources_for_message(message_model, message.sources)

        # Convert back to DTO
        return message_model.to_chat_message()

    def get_messages_of_conversation(self, conversation_id: str) -> list[ChatMessageBase]:
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

        return [message.to_chat_message() for message in messages]

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
        self, message: ChatMessageModel, sources: list[RagChatSource] | None
    ) -> list[ChatMessageSourceModel]:
        """Create source records for a message.

        :param message: The message to attach sources to
        :type message: ChatMessageModel
        :param sources: List of SaveChatMessageSourceDTO
        :type sources: List[SaveChatMessageSourceDTO]
        """

        if not sources:
            return []

        db_sources: list[ChatMessageSourceModel] = []

        for source in sources:
            source_record = ChatMessageSourceModel()
            # use the ID from the DTO object because it is preset to
            # be referenced in the message content
            source_record.id = source.id
            source_record.message = message  # type: ignore
            source_record.document_id = source.document_id
            source_record.document_name = source.document_name
            source_record.score = source.score
            source_record.set_chunk(source.chunk)

            db_sources.append(source_record.save())
        return db_sources

    def set_conversation_external_id(
        self, conversation_id: str, external_id: str
    ) -> ChatConversation:
        """Set the external ID of a conversation.

        :param conversation_id: The ID of the conversation
        :type conversation_id: str
        :param external_id: The external ID to set
        :type external_id: str
        """
        conversation = ChatConversation.get_by_id_and_check(conversation_id)

        if external_id != conversation.external_conversation_id:
            conversation.external_conversation_id = external_id
            conversation.save()

        return conversation

    def get_source_by_id_and_check(self, source_id: str) -> ChatMessageSourceModel:
        """Get a ChatMessageSourceModel by ID and check if it exists.

        :param source_id: The ID of the source
        :type source_id: str
        :return: The ChatMessageSourceModel instance
        :rtype: ChatMessageSourceModel
        :raises NotFoundException: If the source is not found
        """
        return ChatMessageSourceModel.get_by_id_and_check(source_id)

    def _get_current_user(self) -> User:
        current_user = CurrentUserService.get_and_check_current_user()
        return User.from_gws_core_user(current_user)
