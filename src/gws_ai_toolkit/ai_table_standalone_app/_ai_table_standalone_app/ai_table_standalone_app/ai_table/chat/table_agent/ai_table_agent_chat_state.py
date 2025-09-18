from typing import Optional

import reflex as rx
from gws_core import Table

from gws_ai_toolkit._app.chat_base import OpenAiChatStateBase
from gws_ai_toolkit.core.agents.table_agent_ai import TableAgentAi
from gws_ai_toolkit.core.agents.table_agent_ai_events import TableAgentEvent

from ...ai_table_data_state import AiTableDataState
from .ai_table_agent_chat_config import AiTableAgentChatConfig
from .ai_table_agent_chat_config_state import AiTableAgentChatConfigState


class AiTableAgentChatState(OpenAiChatStateBase, rx.State):
    """State management for AI Table Agent Chat - unified table operations functionality.

    This state class manages the AI Table Agent chat workflow, providing intelligent
    routing between data visualization and transformation capabilities through OpenAI
    function calling. The agent automatically determines whether to generate plots
    or transform data based on user requests, then delegates to the appropriate
    specialized agents.

    Key Features:
        - Unified interface for both plotting and transformation operations
        - Intelligent request routing using OpenAI function calling
        - Automatic delegation to PlotlyAgentAi and TableTransformAgentAi
        - Seamless context preservation across different operation types
        - Real-time table updates from transformation operations
        - Conversation history persistence with operation context

    Processing Mode:
        - Function calling: OpenAI determines operation type from user intent
        - Smart delegation: Routes to PlotlyAgentAi or TableTransformAgentAi
        - Result handling: Processes visualization and transformation results
        - State synchronization: Maintains table state across operations

    Inherits from OpenAiChatStateBase providing:
        - OpenAI integration with streaming responses
        - Conversation history integration
        - Error handling and user feedback
        - Message management and chat state
    """

    # UI configuration
    title = "AI Table Operations"
    placeholder_text = "Ask me to visualize or transform your data..."
    empty_state_message = "Start with data visualization or transformation requests"

    _last_response_id: Optional[str] = None

    ANALYSIS_TYPE = "ai_table_unified"

    async def call_ai_chat(self, user_message: str) -> None:
        """Get streaming response from OpenAI about the table data using TableAgentAi"""

        table_agent = await self._get_table_agent()

        # Stream table operation events
        async for event in table_agent.call_agent_async(
            user_query=user_message,
        ):
            await self._handle_table_agent_event(event)

        async with self:
            # Save the TableAgentAi state for continuity in future interactions
            self._last_response_id = table_agent.get_last_response_id()

    async def _handle_table_agent_event(self, event: TableAgentEvent) -> None:
        """Handle events from the unified table agent service"""
        if event.type == "text_delta":
            await self.handle_output_text_delta(event.delta)
        elif event.type == "plot_generated":
            # Handle successful plot generation
            figure = event.figure
            response_id = event.response_id

            async with self:
                message = await self.create_plotly_message(
                    figure=figure,
                    role="assistant",
                    external_id=response_id
                )
                await self.add_message(message)
        elif event.type == "dataframe_transform":
            # Handle successful table transformation
            transformed_table = event.table
            table_name = event.table_name or "Transformed Data"
            response_id = event.response_id

            async with self:
                await self.update_current_table(transformed_table, table_name)

        elif event.type == "error" or event.type == "function_error":
            # Handle errors
            error_message = await self.create_error_message(event.message)
            await self.update_current_response_message(error_message)
        elif event.type == "sub_agent_success":
            # Handle successful sub-agent completion
            await self.close_current_message()
        elif event.type == "response_created":
            if event.response_id is not None:
                await self.handle_response_created_with_id(event.response_id)
        elif event.type == "response_completed":
            await self.handle_response_completed()

    async def handle_response_created_with_id(self, response_id: str) -> None:
        """Handle response created event with response ID"""
        async with self:
            self._current_external_response_id = response_id
            self._previous_external_response_id = response_id

    async def close_current_message(self):
        """Close the current streaming message and add it to the chat history, then save to conversation history."""
        if not self._current_response_message:
            return
        await super().close_current_message()
        # Save conversation after message is added to history
        await self._save_conversation_to_history()

    async def _save_conversation_to_history(self):
        """Save current conversation to history with analysis-specific configuration."""
        config: AiTableAgentChatConfig
        async with self:
            config = await self._get_config()

        # Save conversation to history after response is completed
        await self.save_conversation_to_history(self.ANALYSIS_TYPE, config.to_json_dict())

    async def _get_table_agent(self) -> TableAgentAi:
        """Get or create TableAgentAi instance"""
        async with self:
            openai_client = self._get_openai_client()

            # Get required data
            table = await self._get_current_table()
            if table is None:
                raise ValueError("No active table available for analysis")

            data_state = await self.get_state(AiTableDataState)
            table_name = data_state.current_table_name

            config = await self._get_config()
            table_agent = TableAgentAi(
                openai_client=openai_client,
                table=table,
                model=config.model,
                temperature=config.temperature,
                table_name=table_name
            )

            if self._last_response_id:
                table_agent.set_last_response_id(self._last_response_id)

            return table_agent

    async def _get_config(self) -> AiTableAgentChatConfig:
        """Get configuration for AI Table Agent analysis

        Returns:
            AiTableTableAgentChatConfig: Configuration object for AI Table Agent
        """
        app_config_state = await self.get_state(AiTableAgentChatConfigState)
        return await app_config_state.get_config()

    async def update_current_table(self, new_table: Table, name: str) -> None:
        """Update the active DataFrame with a transformed version"""
        data_state: AiTableDataState = await self.get_state(AiTableDataState)

        # Create a new dataframe item with the transformed data
        data_state.add_table(new_table, name)

    async def _get_current_table(self) -> Optional[Table]:
        """Get the current active table from AiTableDataState

        Returns:
            Optional[Table]: Current table or None if no table is loaded
        """
        data_state = await self.get_state(AiTableDataState)
        return data_state.get_current_table()
