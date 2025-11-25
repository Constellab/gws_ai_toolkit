import os
from typing import TYPE_CHECKING, Literal

import pandas as pd
from pandas import DataFrame

from gws_ai_toolkit.models.chat.message.chat_message_base import ChatMessageBase

if TYPE_CHECKING:
    from gws_ai_toolkit.models.chat.chat_conversation import ChatConversation
    from gws_ai_toolkit.models.chat.chat_message_model import ChatMessageModel


class ChatMessageDataframe(ChatMessageBase):
    """Chat message containing DataFrame content.

    Specialized chat message for pandas DataFrame objects, supporting
    tabular data display in the chat interface. DataFrames are stored
    as CSV files and loaded on demand.

    Attributes:
        type: Fixed as "dataframe" to identify this as a dataframe message
        dataframe: The pandas DataFrame object (may be None if not loaded)

    Example:
        df_msg = ChatMessageDataframe(
            role="assistant",
            id="msg_df_123",
            dataframe=pd.DataFrame({'A': [1, 2], 'B': [3, 4]})
        )
    """

    type: Literal["dataframe"] = "dataframe"
    role: Literal["assistant"] = "assistant"
    dataframe: DataFrame | None = None
    content: str | None = None  # additional member
    dataframe_name: str | None = None

    class Config:
        arbitrary_types_allowed = True

    def fill_from_model(self, chat_message: "ChatMessageModel") -> None:
        """Fill additional fields from the ChatMessageModel.
        This is called after the initial creation in from_chat_message_model.
        """
        file_path = chat_message.get_filepath_if_exists()
        if file_path:
            try:
                self.dataframe = pd.read_csv(file_path)
            except Exception:
                self.dataframe = None
        else:
            self.dataframe = None

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
            content=self.content,
            external_id=self.external_id,
            data={"dataframe_name": self.dataframe_name} if self.dataframe_name else {},
        )

        # Save dataframe to folder if present
        if self.dataframe is not None:
            self._save_dataframe_to_message(message)

        return message

    def _save_dataframe_to_message(self, message: "ChatMessageModel") -> None:
        """Save the DataFrame to the conversation folder and update message filename.

        :param message: The ChatMessage instance to save the dataframe for
        :type message: ChatMessage
        """
        if self.dataframe is None:
            return

        folder_path = message.conversation.get_conversation_folder_path()

        # Ensure folder exists
        os.makedirs(folder_path, exist_ok=True)

        # Generate unique filename
        filename = f"dataframe_{message.id}.csv"
        file_path = os.path.join(folder_path, filename)

        # Save DataFrame as CSV
        self.dataframe.to_csv(file_path, index=False)

        message.filename = filename
