from collections.abc import Generator

from gws_ai_toolkit.core.agents.base_function_agent_events import (
    FunctionCallEvent,
    FunctionErrorEvent,
    FunctionSuccessEvent,
)
from gws_ai_toolkit.core.agents.table.table_agent_ai import TableAgentAi
from gws_ai_toolkit.core.agents.table.table_agent_ai_events import TableAgentEvent
from gws_ai_toolkit.core.agents.table.table_agent_event_base import UserQueryMultiTablesEvent
from gws_ai_toolkit.models.chat.message.chat_message_base import ChatMessageBase
from gws_ai_toolkit.models.chat.message.chat_message_error import ChatMessageError
from gws_ai_toolkit.models.chat.message.chat_message_plotly import ChatMessagePlotly
from gws_ai_toolkit.models.chat.message.chat_message_table import ChatMessageTable
from gws_ai_toolkit.models.chat.message.chat_message_tool_call import ChatMessageToolCall
from gws_ai_toolkit.models.chat.message.chat_message_types import ChatMessage
from gws_ai_toolkit.models.chat.message.chat_user_message_table import ChatUserMessageTable

from .base_chat_conversation import (
    BaseChatConversation,
    BaseChatConversationConfig,
    ChatConversationMode,
)
from .chat_message_history_mapper import ChatMessageHistoryMapper


class AiTableAgentChatConversation(BaseChatConversation[ChatUserMessageTable]):
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
    _tool_names_by_call_id: dict[str, str]

    def __init__(self, config: BaseChatConversationConfig, table_agent: TableAgentAi) -> None:
        super().__init__(
            config,
            mode=ChatConversationMode.AI_TABLE.value,
            chat_configuration={
                "model": table_agent.get_model(),
                "temperature": table_agent.get_temperature(),
            },
        )
        self.table_agent = table_agent
        self._current_external_response_id = None
        self._tool_names_by_call_id = {}

    def _call_ai_chat(
        self, user_message: ChatUserMessageTable
    ) -> Generator[ChatMessage, None, None]:
        """Handle user message and call AI chat service using TableAgentAi.

        Routes requests through the TableAgentAi which intelligently delegates
        to either PlotlyAgentAi (for visualizations) or TableTransformAgentAi
        (for data transformations) based on user intent.

        Args:
            user_message: The message from the user

        Yields:
            ChatMessageDTO: The current message being streamed with updated content
        """

        # Note: user_message is already saved by call_conversation() in the base class
        # so we don't need to save it again here
        yield user_message

        user_query = UserQueryMultiTablesEvent(
            query=user_message.content, tables=user_message.tables, agent_id=self.table_agent.id
        )

        # Process table agent events synchronously
        for event in self.table_agent.call_agent(user_query):
            messages = self._handle_table_agent_event(event)
            yield from messages

    def _handle_table_agent_event(self, event: TableAgentEvent) -> list[ChatMessage]:
        """Handle events from the unified table agent service.

        Returns all new messages for UI updates.

        Args:
            event: The TableAgentEvent to handle

        Returns:
            list[AllChatMessages]: A list of messages (empty list if no messages to return)
        """
        self._record_tool_turn(event)

        if event.type == "text_delta":
            message = self.build_current_message(
                event.delta, external_id=self._current_external_response_id
            )
            return [message] if message else []

        elif event.type == "plot_generated":
            # Handle successful plot generation
            if not event.plot:
                return []

            plotly_message = ChatMessagePlotly(plot=event.plot, external_id=event.response_id)
            saved_message = self.save_message(message=plotly_message)
            return [saved_message]

        elif event.type == "dataframe_transform":
            # Handle successful table transformation
            transformed_table = event.table
            if not event.table.name:
                event.table.name = "Transformed Data"

            message = ChatMessageTable(
                table=transformed_table,
                external_id=event.response_id,
            )
            saved_message = self.save_message(message=message)
            return [saved_message]

        elif event.type == "multi_table_transform":
            # Handle successful multi-table transformation - create separate message for each table
            transformed_tables = event.tables
            messages = []

            for table_name, table in transformed_tables.items():
                if not table.name:
                    table.name = table_name
                dataframe_message = ChatMessageTable(
                    table=table,
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

    def _record_tool_turn(self, event: TableAgentEvent) -> None:
        """Persist the tool turns of this conversation's own agent, in stream order.

        Only the orchestrator's turns are recorded. Its sub-agents are created fresh for each
        tool call and carry their own history, so persisting their calls here would replay one
        agent's work into another agent's context.

        Args:
            event: The event being handled.
        """
        if getattr(event, "agent_id", None) != self.table_agent.id:
            return

        if isinstance(event, FunctionCallEvent):
            self._tool_names_by_call_id[event.call_id] = event.function_name
            self.save_tool_call(
                tool_name=event.function_name,
                args=event.arguments,
                tool_call_id=event.call_id,
                external_id=event.response_id,
            )

        elif isinstance(event, FunctionSuccessEvent):
            self._save_tool_result_for_call(
                event.call_id, event.function_response, event.response_id
            )

        elif isinstance(event, FunctionErrorEvent):
            # The model was handed this error and asked to correct itself, so it is the result of
            # that call as far as the history is concerned. Recording it keeps the call paired,
            # which a run that recovered from a tool error would otherwise leave dangling.
            self._save_tool_result_for_call(event.call_id, event.message, event.response_id)

    def _save_tool_result_for_call(
        self, call_id: str, content: str, response_id: str | None
    ) -> None:
        """Persist a tool result, resolving the tool name from the call it answers.

        Args:
            call_id: The call this result answers.
            content: What the tool reported back to the model.
            response_id: Id of the response that made the call.
        """
        tool_name = self._tool_names_by_call_id.get(call_id)
        if not tool_name:
            # A result with no recorded call cannot be paired, and an unpaired result is dropped
            # on restore anyway.
            return

        self.save_tool_result(
            tool_name=tool_name,
            content=content,
            tool_call_id=call_id,
            external_id=response_id,
        )

    def _restore_agent_history(self, messages: list[ChatMessageBase]) -> None:
        """Hand the agent back the history rebuilt from the persisted messages.

        Args:
            messages: The conversation's persisted messages, oldest first.
        """
        self.table_agent.set_message_history(ChatMessageHistoryMapper.to_model_messages(messages))
        self._tool_names_by_call_id = {
            message.tool_call_id: message.tool_name
            for message in messages
            if isinstance(message, ChatMessageToolCall)
        }
