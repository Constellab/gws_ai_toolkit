from collections.abc import Generator

from gws_ai_toolkit.core.agents.table_agent_ai import TableAgentAi
from gws_ai_toolkit.core.agents.table_agent_ai_events import TableAgentEvent
from gws_ai_toolkit.models.chat.message.chat_message_dataframe import ChatMessageDataframe
from gws_ai_toolkit.models.chat.message.chat_message_error import ChatMessageError
from gws_ai_toolkit.models.chat.message.chat_message_plotly import ChatMessagePlotly
from gws_ai_toolkit.models.chat.message.chat_message_types import AllChatMessages

from .base_chat_conversation import BaseChatConversation, BaseChatConversationConfig


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
        table_agent: The TableAgentAi instance to use for operations
        _current_external_response_id: Current response ID being processed
    """

    table_agent: TableAgentAi

    _current_external_response_id: str | None = None

    def __init__(self, config: BaseChatConversationConfig, table_agent: TableAgentAi) -> None:
        super().__init__(
            config,
            mode="ai_table_unified",
            chat_configuration={
                "model": table_agent.get_model(),
                "temperature": table_agent.get_temperature(),
            },
        )
        self.table_agent = table_agent
        self._current_external_response_id = None

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

        # Process table agent events synchronously
        for event in self.table_agent.call_agent(user_message):
            messages = self._handle_table_agent_event(event)
            yield from messages

    def _handle_table_agent_event(self, event: TableAgentEvent) -> list[AllChatMessages]:
        """Handle events from the unified table agent service.

        Returns all new messages for UI updates.

        Args:
            event: The TableAgentEvent to handle

        Returns:
            list[AllChatMessages]: A list of messages (empty list if no messages to return)
        """
        if event.type == "text_delta":
            message = self.build_current_message(event.delta, external_id=self._current_external_response_id)
            return [message] if message else []

        elif event.type == "plot_generated":
            # Handle successful plot generation
            if not event.figure:
                return []

            plotly_message = ChatMessagePlotly(figure=event.figure, external_id=event.response_id)
            saved_message = self.save_message(message=plotly_message)
            return [saved_message]

        elif event.type == "dataframe_transform":
            # Handle successful table transformation
            transformed_table = event.table
            new_table_name = event.table_name or "Transformed Data"

            hint_message = ChatMessageDataframe(
                dataframe=transformed_table.get_data(),
                dataframe_name=new_table_name,
                external_id=event.response_id,
            )
            saved_message = self.save_message(message=hint_message)
            return [saved_message]

        elif event.type == "multi_table_transform":
            # Handle successful multi-table transformation - create separate message for each table
            transformed_tables = event.tables
            messages = []

            for table_name, table in transformed_tables.items():
                dataframe_message = ChatMessageDataframe(
                    dataframe=table.get_data(),
                    dataframe_name=table_name,
                    external_id=event.response_id,
                )
                saved_message = self.save_message(message=dataframe_message)
                messages.append(saved_message)
            return messages
        # For now we hide code messages
        # elif event.type == "code":
        #     code_message = ChatMessageCode(
        #         code=event.code,
        #         external_id=event.response_id,
        #     )
        #     saved_message = self.save_message(message=code_message)
        #     return [saved_message]

        elif event.type in {"error", "function_error"}:
            # Handle errors
            error_message = ChatMessageError(
                error=event.message,
                external_id=getattr(event, "response_id", None),
            )
            saved_message = self.save_message(message=error_message)
            return [saved_message]

        elif event.type == "sub_agent_success":
            # Handle successful sub-agent completion
            message = self.close_current_message(external_id=self._current_external_response_id)
            return [message] if message else []

        elif event.type == "response_created":
            if event.response_id is not None:
                self._current_external_response_id = event.response_id
            return []

        elif event.type == "response_completed":
            self._current_external_response_id = None
            message = self.close_current_message(external_id=self._current_external_response_id)
            return [message] if message else []

        return []
