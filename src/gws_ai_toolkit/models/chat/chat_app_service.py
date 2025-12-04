from typing import Optional

from gws_core import NotFoundException

from gws_ai_toolkit.core.ai_toolkit_db_manager import AiToolkitDbManager
from gws_ai_toolkit.models.chat.chat_app import ChatApp
from gws_ai_toolkit.models.chat.chat_app_dto import SaveChatAppDTO


class ChatAppService:
    """Service class for managing chat applications.

    Provides methods to create, retrieve, and manage ChatApp instances.
    """

    @AiToolkitDbManager.transaction()
    def create(self, chat_app_dto: SaveChatAppDTO) -> ChatApp:
        """Create a chat app. Does nothing if the ChatApp with the same name already exists.

        :param chat_app_dto: The chat app data to create
        :type chat_app_dto: SaveChatAppDTO
        :return: The existing or newly created ChatApp
        :rtype: ChatApp
        """
        # Check if a chat app with this name already exists
        existing_app = ChatApp.get_or_none(ChatApp.name == chat_app_dto.name)

        if existing_app:
            # Return the existing app without creating a new one
            return existing_app

        # Create new chat app
        chat_app = ChatApp()
        chat_app.name = chat_app_dto.name
        chat_app.save()

        return chat_app

    def get_by_id(self, chat_app_id: str) -> Optional[ChatApp]:
        """Get a chat app by ID.

        :param chat_app_id: The ID of the chat app to retrieve
        :type chat_app_id: str
        :return: The ChatApp if found, None otherwise
        :rtype: Optional[ChatApp]
        """
        return ChatApp.get_by_id(chat_app_id)

    def get_and_check(self, chat_app_id: str) -> ChatApp:
        """Get a chat app by ID and check if it exists.

        :param chat_app_id: The ID of the chat app to retrieve
        :type chat_app_id: str
        :return: The ChatApp
        :rtype: ChatApp
        :raises NotFoundException: If the chat app is not found
        """
        return ChatApp.get_by_id_and_check(chat_app_id)

    def get_by_name(self, name: str) -> Optional[ChatApp]:
        """Get a chat app by name.

        :param name: The name of the chat app to retrieve
        :type name: str
        :return: The ChatApp if found, None otherwise
        :rtype: Optional[ChatApp]
        """
        return ChatApp.get_or_none(ChatApp.name == name)

    def get_by_name_and_check(self, name: str) -> ChatApp:
        """Get a chat app by name and check if it exists.

        :param name: The name of the chat app to retrieve
        :type name: str
        :return: The ChatApp
        :rtype: ChatApp
        :raises NotFoundException: If the chat app is not found
        """
        chat_app = self.get_by_name(name)
        if not chat_app:
            raise NotFoundException(f"ChatApp with name '{name}' not found.")
        return chat_app

    def get_or_create(self, name: str) -> ChatApp:
        """Get a chat app by name or create it if it doesn't exist.

        :param name: The name of the chat app
        :type name: str
        :return: The existing or newly created ChatApp
        :rtype: ChatApp
        """
        chat_app_dto = SaveChatAppDTO(name=name)
        return self.create(chat_app_dto)

    @AiToolkitDbManager.transaction()
    def delete(self, chat_app_id: str) -> None:
        """Delete a chat app by ID.

        :param chat_app_id: The ID of the chat app to delete
        :type chat_app_id: str
        :raises NotFoundException: If the chat app is not found
        """
        chat_app = self.get_and_check(chat_app_id)
        chat_app.delete_instance()
