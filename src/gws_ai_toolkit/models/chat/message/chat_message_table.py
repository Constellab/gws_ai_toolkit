import os
from typing import TYPE_CHECKING, Literal

import pandas as pd
from gws_core import Table

from gws_ai_toolkit.models.chat.message.chat_message_base import ChatMessageBase

if TYPE_CHECKING:
    from gws_ai_toolkit.models.chat.chat_conversation import ChatConversation
    from gws_ai_toolkit.models.chat.chat_message_model import ChatMessageModel


class ChatMessageTable(ChatMessageBase):
    """Chat message containing DataFrame content.

    Specialized chat message for pandas DataFrame objects, supporting
    tabular data display in the chat interface. DataFrames are stored
    as CSV files and loaded on demand.

    Attributes:
        type: Fixed as "dataframe" to identify this as a dataframe message
        dataframe: The pandas DataFrame object (may be None if not loaded)

    Example:
        df_msg = ChatMessageTable(
            role="assistant",
            id="msg_df_123",
            dataframe=pd.DataFrame({'A': [1, 2], 'B': [3, 4]})
        )
    """

    type: Literal["table"] = "table"
    role: Literal["assistant"] = "assistant"
    content: str | None = None
    table: Table | None = None

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
            data={"table_name": self.table.name} if self.table else {},
        )

        # Save dataframe to folder if present
        if self.dataframe is not None:
            self._save_table_to_message(message)

        return message

    def _save_table_to_message(self, message: "ChatMessageModel") -> None:
        """Save the DataFrame to the conversation folder and update message filename.

        :param message: The ChatMessage instance to save the dataframe for
        :type message: ChatMessage
        """
        if self.table is None:
            return

        folder_path = message.conversation.get_conversation_folder_path()

        # Ensure folder exists
        os.makedirs(folder_path, exist_ok=True)

        # Generate unique filename
        filename = f"table_{message.id}.csv"
        file_path = os.path.join(folder_path, filename)

        # Save DataFrame as CSV
        self.table.get_data().to_csv(file_path, index=False)

        message.filename = filename

    def to_front_dto(self) -> ChatMessageBase:
        return ChatMessageTableFront(
            id=self.id,
            content=self.content if self.content else "",
            table_id=self.table.uid if self.table else "",
            table_name=self.table.name if self.table else "Table",
        )


class ChatMessageTableFront(ChatMessageBase):
    type: Literal["table"] = "table"
    role: Literal["assistant"] = "assistant"
    content: str
    table_id: str
    table_name: str
