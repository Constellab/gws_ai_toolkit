from typing import TYPE_CHECKING, ClassVar, Literal

from gws_core import BaseModelDTO, UserDTO

if TYPE_CHECKING:
    from gws_ai_toolkit.models.chat.chat_conversation import ChatConversation
    from gws_ai_toolkit.models.chat.chat_message_model import ChatMessageModel


class ChatMessageBase(BaseModelDTO):
    """Base chat message class for all message types in the chat system.

    This class serves as the foundation for all chat messages, providing common
    attributes and functionality shared across different message types (text,
    image, code). It integrates with the RAG system to support source citations
    and handles various content types.

    Attributes:
        role (Literal['user', 'assistant']): Message sender - either user or AI assistant
        type (Literal["text", "image", "code"]): Content type for proper rendering
        content (Any): Message content - varies by message type
        id (str): Unique identifier for the message
        external_id (Optional[str]): Optional external system ID (from openai, dify, ragflow...) for the message
        sources (Optional[List[RagChatSource]]): Source citations for RAG responses

    Features:
        - Flexible content handling for different message types
        - Source citation support for RAG-enhanced responses
        - Role-based message identification
        - Unique message identification
        - File path support for image content

    Example:
        message = ChatMessage(
            role="assistant",
            type="text",
            content="Hello, how can I help?",
            id="msg_123",
            sources=[source1, source2]
        )
    """

    id: str | None = None
    role: Literal["user", "assistant"] = "assistant"
    external_id: str | None = None
    user: UserDTO | None = None

    # Class registry for type-to-class mapping
    _type_registry: ClassVar[dict[str, type["ChatMessageBase"]]] = {}

    def is_user_message(self) -> bool:
        """Check if this message was sent by the user.

        Returns:
            bool: True if message role is 'user', False if 'assistant'
        """
        return self.role == "user"

    @classmethod
    def register_type(cls, message_type: str, message_class: type["ChatMessageBase"]) -> None:
        """Register a message class for a specific message type.

        :param message_type: The type identifier (e.g., 'text', 'image')
        :type message_type: str
        :param message_class: The class to use for this message type
        :type message_class: type[ChatMessageBase]
        """
        cls._type_registry[message_type] = message_class

    @classmethod
    def from_chat_message_model(cls, chat_message: "ChatMessageModel") -> "ChatMessageBase":
        """Convert database ChatMessage model to ChatMessageBase union type.

        Uses the registered message classes to delegate conversion to the appropriate subclass.

        :param chat_message: The database ChatMessage instance to convert
        :type chat_message: ChatMessage
        :return: ChatMessageBase union type instance
        :rtype: ChatMessageBase
        """
        # Import here to avoid circular imports

        # Handle user messages
        message_class = cls._type_registry.get(chat_message.type)

        if not message_class:
            raise ValueError(f"Unsupported chat message type: {chat_message.type}")

        # create the object with basic fields
        message = message_class(
            id=chat_message.id,
            external_id=chat_message.external_id,
            user=chat_message.user.to_dto(),
        )

        message.fill_from_model(chat_message)

        return message

    def fill_from_model(self, chat_message: "ChatMessageModel") -> None:
        """Fill additional fields from the ChatMessageModel.
        This is called after the initial creation in from_chat_message_model.
        """

    def to_chat_message_model(self, conversation: "ChatConversation") -> "ChatMessageModel":
        """Convert DTO to database ChatMessage model.

        Must be implemented by subclasses.

        :param conversation: The conversation this message belongs to
        :type conversation: ChatConversation
        :return: ChatMessage database model instance
        :rtype: ChatMessage
        """
        raise NotImplementedError("Subclasses must implement to_chat_message")

    def to_front_dto(self) -> "ChatMessageBase":
        """Convert to front-end DTO representation.

        This method can be overridden by subclasses to provide
        specific front-end representations if needed.

        :return: The front-end DTO representation of the message
        :rtype: ChatMessageBase
        """
        return self
