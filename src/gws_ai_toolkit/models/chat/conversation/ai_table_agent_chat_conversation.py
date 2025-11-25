import os
from collections.abc import Generator

from gws_core import BaseModelDTO, Table
from openai import OpenAI

from gws_ai_toolkit.core.agents.table_agent_ai import TableAgentAi
from gws_ai_toolkit.core.agents.table_agent_ai_events import TableAgentEvent
from gws_ai_toolkit.models.chat.message import (
    AllChatMessages,
    ChatMessageDataframe,
    ChatMessageError,
    ChatMessagePlotly,
)

from .base_chat_conversation import BaseChatConversation


class AiTableAgentChatConfig(BaseModelDTO):
    """Configuration for AI Table Agent Chat."""

    model: str = "gpt-4o"
    temperature: float = 0.3


class AiTableAgentChatConversation(BaseChatConversation):
    """Chat conversation implementation for AI Table Agent operations.

    This class handles AI-powered table operations (visualization and transformation)
    using the TableAgentAi. It provides intelligent routing between plot generation
    and data transformation based on user requests.

    Key Features:
        - Unified interface for both plotting and transformation operations
        - Intelligent request routing using OpenAI function calling
        - Automatic delegation to PlotlyAgentAi and TableTransformAgentAi
        - Real-time table updates from transformation operations
        - Streaming responses with message yielding
        - Conversation persistence

    Attributes:
        config: Configuration for the AI chat (model, temperature)
        table: The Table to analyze
        table_name: Optional name for the table
        on_table_transform: Optional callback when table is transformed
        _last_response_id: For conversation continuity
        _current_external_response_id: Current response ID being processed
    """

    config: AiTableAgentChatConfig
    table: Table
    table_name: str | None

    _last_response_id: str | None = None
    _current_external_response_id: str | None = None

    def __init__(
        self,
        chat_app_name: str,
        config: AiTableAgentChatConfig,
        table: Table,
        table_name: str | None = None,
    ) -> None:
        super().__init__(chat_app_name, config.to_json_dict(), "ai_table_unified")
        self.config = config
        self.table = table
        self.table_name = table_name
        self._last_response_id = None
        self._current_external_response_id = None

    def _get_openai_client(self) -> OpenAI:
        """Get OpenAI client with API key."""
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise ValueError("OpenAI API key is not set")
        return OpenAI(api_key=api_key)

    def set_table(self, table: Table, table_name: str | None = None) -> None:
        """Update the table to analyze.

        Args:
            table: The new Table to analyze
            table_name: Optional name for the table
        """
        self.table = table
        if table_name:
            self.table_name = table_name

    def call_ai_chat(self, user_message: str) -> Generator[AllChatMessages, None, None]:
        """Handle user message and call AI chat service using TableAgentAi.

        Routes requests through the TableAgentAi which intelligently delegates
        to either PlotlyAgentAi (for visualizations) or TableTransformAgentAi
        (for data transformations) based on user intent.

        Args:
            user_message: The message from the user

        Yields:
            ChatMessageDTO: The current message being streamed with updated content
        """
        table_agent = self._get_table_agent()

        # Process table agent events synchronously
        for event in table_agent.call_agent(user_message):
            message = self._handle_table_agent_event(event)
            if message:
                yield message

        # Save the response ID for conversation continuity
        self._last_response_id = table_agent.get_last_response_id()

    def _get_table_agent(self) -> TableAgentAi:
        """Get or create TableAgentAi instance."""
        openai_client = self._get_openai_client()

        if self.table is None:
            raise ValueError("No active table available for analysis")

        table_agent = TableAgentAi(
            openai_client=openai_client,
            table=self.table,
            model=self.config.model,
            temperature=self.config.temperature,
            table_name=self.table_name,
        )

        if self._last_response_id:
            table_agent.set_last_response_id(self._last_response_id)

        return table_agent

    def _handle_table_agent_event(self, event: TableAgentEvent) -> AllChatMessages | None:
        """Handle events from the unified table agent service.

        Yields all new messages for UI updates.

        Args:
            event: The TableAgentEvent to handle

        Returns:
            Optional[AllChatMessages]: A message to yield, or None
        """
        if event.type == "text_delta":
            return self.build_current_message(event.delta, external_id=self._current_external_response_id)

        elif event.type == "plot_generated":
            # Handle successful plot generation
            if not event.figure:
                return None

            plotly_message = ChatMessagePlotly(figure=event.figure, external_id=event.response_id)
            saved_message = self._conversation_service.save_message(
                conversation_id=self._conversation.id, message=plotly_message
            )
            return saved_message

        elif event.type == "dataframe_transform":
            # Handle successful table transformation
            transformed_table = event.table
            new_table_name = event.table_name or "Transformed Data"

            # Update internal table
            self.table = transformed_table
            self.table_name = new_table_name

            hint_message = ChatMessageDataframe(
                dataframe=transformed_table.get_data(),
                dataframe_name=new_table_name,
                external_id=event.response_id,
            )
            saved_message = self._conversation_service.save_message(
                conversation_id=self._conversation.id, message=hint_message
            )
            return saved_message

        elif event.type == "error" or event.type == "function_error":
            # Handle errors
            error_message = ChatMessageError(
                error=event.message,
                external_id=getattr(event, "response_id", None),
            )
            saved_message = self._conversation_service.save_message(
                conversation_id=self._conversation.id, message=error_message
            )
            return saved_message

        elif event.type == "sub_agent_success":
            # Handle successful sub-agent completion
            return self.close_current_message(external_id=self._current_external_response_id)

        elif event.type == "response_created":
            if event.response_id is not None:
                self._current_external_response_id = event.response_id
            return None

        elif event.type == "response_completed":
            self._current_external_response_id = None
            return self.close_current_message(external_id=self._current_external_response_id)

        return None
