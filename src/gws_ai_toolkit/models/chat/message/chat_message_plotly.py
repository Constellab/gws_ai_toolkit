import os
from typing import TYPE_CHECKING, Literal

import plotly.graph_objects as go
import plotly.io as pio

from gws_ai_toolkit.models.chat.message.chat_message_base import ChatMessageBase

if TYPE_CHECKING:
    from gws_ai_toolkit.models.chat.chat_conversation import ChatConversation
    from gws_ai_toolkit.models.chat.chat_message_model import ChatMessageModel


class ChatMessagePlotly(ChatMessageBase):
    """Chat message containing Plotly figure content.

    Specialized chat message for interactive Plotly visualizations created
    through function calls. Used to display charts, graphs, and data
    visualizations in the chat interface.

    Attributes:
        type: Fixed as "plotly" to identify this as a plotly message
        figure: The Plotly figure object for rendering (may be None if not loaded)

    Example:
        plotly_msg = ChatMessagePlotly(
            role="assistant",
            id="msg_plotly_123",
            figure=go.Figure(data=[go.Bar(x=['A', 'B'], y=[1, 2])])
        )
    """

    type: Literal["plotly"] = "plotly"
    role: Literal["assistant"] = "assistant"
    figure: go.Figure | None = None

    class Config:
        arbitrary_types_allowed = True

    def fill_from_model(self, chat_message: "ChatMessageModel") -> None:
        """Fill additional fields from the ChatMessageModel.
        This is called after the initial creation in from_chat_message_model.
        """
        file_path = chat_message.get_filepath_if_exists()
        if file_path:
            # Load figure from file
            try:
                self.figure = pio.read_json(file_path)
            except Exception:
                self.figure = None
        else:
            self.figure = None

    def _save_figure_to_message(self, message: "ChatMessageModel") -> None:
        """Save the Plotly figure to the conversation folder and update message filename.

        :param message: The ChatMessage instance to save the figure for
        :type message: ChatMessage
        """
        if not self.figure:
            return

        folder_path = message.conversation.get_conversation_folder_path()

        # Ensure folder exists
        os.makedirs(folder_path, exist_ok=True)

        # Generate unique filename
        filename = f"plot_{message.id}.json"
        file_path = os.path.join(folder_path, filename)

        # Save figure as JSON
        pio.write_json(self.figure, file_path)

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

        # Save figure to folder if present
        if self.figure:
            self._save_figure_to_message(message)

        return message
