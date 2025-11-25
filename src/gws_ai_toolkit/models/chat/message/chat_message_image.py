import os
from typing import TYPE_CHECKING, Literal

from PIL import Image

from gws_ai_toolkit.models.chat.message.chat_message_base import ChatMessageBase

if TYPE_CHECKING:
    from gws_ai_toolkit.models.chat.chat_conversation import ChatConversation
    from gws_ai_toolkit.models.chat.chat_message_model import ChatMessageModel


class ChatMessageImage(ChatMessageBase):
    """Chat message containing image content.

    Specialized chat message for images, supporting PIL Image objects.
    Images are stored as files in the conversation folder and loaded on demand.

    Attributes:
        type: Fixed as "image" to identify this as an image message
        image: The PIL Image object (may be None if not loaded)

    Example:
        image_msg = ChatMessageImage(
            role="assistant",
            id="msg_image_123",
            image=Image.open("chart.png")
        )
    """

    type: Literal["image"] = "image"
    role: Literal["assistant"] = "assistant"

    image: Image.Image | None = None

    class Config:
        arbitrary_types_allowed = True

    def fill_from_model(self, chat_message: "ChatMessageModel") -> None:
        """Fill additional fields from the ChatMessageModel.
        This is called after the initial creation in from_chat_message_model.
        """
        file_path = chat_message.get_filepath_if_exists()
        if file_path:
            # Load image from file
            try:
                self.image = Image.open(file_path)
            except Exception:
                self.image = None
        else:
            self.image = None

    def _save_image_to_message(self, message: "ChatMessageModel") -> None:
        """Save the image to the conversation folder and update message filename.

        :param message: The ChatMessage instance to save the image for
        :type message: ChatMessage
        """
        if not self.image:
            return

        folder_path = message.conversation.get_conversation_folder_path()

        # Ensure folder exists
        os.makedirs(folder_path, exist_ok=True)

        # Generate unique filename
        filename = f"image_{message.id}.png"
        file_path = os.path.join(folder_path, filename)

        # Save image
        self.image.save(file_path, format="PNG")

        message.filename = filename

    def to_chat_message_model(self, conversation: "ChatConversation") -> "ChatMessageModel":
        """Convert DTO to database ChatMessage model.

        :param conversation: The conversation this message belongs to
        :type conversation: ChatConversation
        :return: ChatMessage database model instance
        :rtype: ChatMessage
        """
        from gws_ai_toolkit.models.chat.chat_message_model import ChatMessageModel

        message = ChatMessageModel.build_message(
            conversation=conversation,
            role=self.role,
            type_=self.type,
            content="",
            external_id=self.external_id,
        )

        # Save image to folder if present
        if self.image:
            self._save_image_to_message(message)

        return message
