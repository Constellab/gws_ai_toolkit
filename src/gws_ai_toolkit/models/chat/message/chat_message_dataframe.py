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
    dataframe: DataFrame | None
    content: str | None = None  # additional member
    dataframe_name: str | None = None

    class Config:
        arbitrary_types_allowed = True

    @classmethod
    def from_chat_message_model(cls, chat_message: "ChatMessageModel") -> "ChatMessageDataframe":
        """Convert database ChatMessage model to ChatMessageDataframe DTO.

        :param chat_message: The database ChatMessage instance to convert
        :type chat_message: ChatMessage
        :return: ChatMessageDataframe DTO instance
        :rtype: ChatMessageDataframe
        """
        sources = [source.to_rag_dto() for source in chat_message.sources]
        dataframe: DataFrame | None = None

        file_path = chat_message._get_filepath_if_exists()
        if file_path:
            try:
                dataframe = pd.read_csv(file_path)
            except Exception:
                dataframe = None

        return cls(
            id=chat_message.id,
            external_id=chat_message.external_id,
            sources=sources,
            dataframe=dataframe,
            content=chat_message.message,
            dataframe_name=chat_message.data.get("dataframe_name", None),
        )

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
