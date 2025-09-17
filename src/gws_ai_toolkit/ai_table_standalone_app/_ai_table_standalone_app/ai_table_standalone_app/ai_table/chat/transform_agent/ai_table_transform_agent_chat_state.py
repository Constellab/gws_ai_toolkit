from typing import Optional

import reflex as rx
from gws_core import Table

from gws_ai_toolkit._app.chat_base import OpenAiChatStateBase
from gws_ai_toolkit.core.agents.table_transform_agent_ai import \
    TableTransformAgentAi
from gws_ai_toolkit.core.agents.table_transform_agent_ai_events import \
    DataFrameTransformAgentEvent

from ...ai_table_data_state import AiTableDataState
from .ai_table_transform_agent_chat_config import \
    AiTableTransformAgentChatConfig
from .ai_table_transform_agent_chat_config_state import \
    AiTableTransformAgentChatConfigState


class AiTableTransformAgentChatState(OpenAiChatStateBase, rx.State):
    """State management for AI Table Transform Agent Chat - specialized DataFrame transformation functionality.

    This state class manages the AI Table Transform Agent chat workflow, providing intelligent
    DataFrame transformation capabilities focused on cleaning, manipulating, and transforming
    tabular data. It integrates with OpenAI's API to generate and execute pandas code for
    data transformations.

    Key Features:
        - DataFrame transformation through natural language requests
        - Code generation for pandas operations (cleaning, filtering, aggregation, etc.)
        - Real-time data transformation with immediate DataFrame updates
        - Conversation history persistence with transformation context
        - Error handling and validation for generated code
        - Support for complex data operations (merge, pivot, group by, etc.)

    Processing Mode:
        - Metadata-aware: Uses table structure and metadata for intelligent transformations
        - Code generation: OpenAI generates pandas code for requested transformations
        - Local execution: Generated code is executed locally with the actual DataFrame
        - Result validation: Ensures transformations produce valid DataFrames

    Inherits from OpenAiChatStateBase providing:
        - OpenAI integration with streaming responses
        - Conversation history integration
        - Error handling and user feedback
        - Message management and chat state
    """

    # UI configuration
    title = "AI DataFrame Transformer"
    placeholder_text = "Ask me to transform, clean, or manipulate this data..."
    empty_state_message = "Start transforming your DataFrame"

    _last_response_id: Optional[str] = None

    ANALYSIS_TYPE = "ai_table_transform"

    async def call_ai_chat(self, user_message: str) -> None:
        """Get streaming response from OpenAI for DataFrame transformation using Transform Agent"""

        transform_agent = await self._get_transform_agent()

        # Stream transformation events
        for event in transform_agent.call_agent(
            user_query=user_message,
        ):
            await self._handle_transform_agent_event(event)

        async with self:
            # Save the DataFrameTransformAgentAi state for continuity in future interactions
            self._last_response_id = transform_agent.get_last_response_id()

    async def _handle_transform_agent_event(self, event: DataFrameTransformAgentEvent) -> None:
        """Handle events from the transform agent service"""
        if event.type == "text_delta":
            await self.handle_output_text_delta(event.delta)
        elif event.type == "dataframe_transform":
            async with self:
                # Update the active DataFrame with the transformed version
                await self.update_current_table(event.table, event.table_name or "Transformed Table")

        elif event.type == "error" or event.type == "function_error":
            # Handle errors
            error_message = await self.create_error_message(event.message)
            await self.update_current_response_message(error_message)

        elif event.type == "output_item_added":
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
        config: AiTableTransformAgentChatConfig
        async with self:
            config = await self._get_config()

        # Save conversation to history after response is completed
        await self.save_conversation_to_history(self.ANALYSIS_TYPE, config.to_json_dict())

    async def _get_transform_agent(self) -> TableTransformAgentAi:
        """Get or create DataFrameTransformAgentAi instance"""
        async with self:
            openai_client = self._get_openai_client()

            # Get required data
            table = await self._get_current_table()
            if table is None:
                raise ValueError("No active dataframe available for transformation")

            config = await self._get_config()
            table_agent = TableTransformAgentAi(
                openai_client=openai_client,
                table=table,
                model=config.model,
                temperature=config.temperature,
                table_name=table.name
            )

            if self._last_response_id:
                table_agent.set_last_response_id(self._last_response_id)

            return table_agent

    async def _get_config(self) -> AiTableTransformAgentChatConfig:
        """Get configuration for AI Table Transform Agent analysis

        Returns:
            AiTableTransformAgentChatConfig: Configuration object for AI Table Transform Agent
        """
        app_config_state = await self.get_state(AiTableTransformAgentChatConfigState)
        config = await app_config_state.get_config()
        return config

    async def _get_current_table(self) -> Optional[Table]:
        """Get the active DataFrame for the currently active table (original or subtable)"""
        data_state: AiTableDataState = await self.get_state(AiTableDataState)

        return data_state.get_current_table()

    async def update_current_table(self, new_table: Table, name: str) -> None:
        """Update the active DataFrame with a transformed version"""
        data_state: AiTableDataState = await self.get_state(AiTableDataState)

        # Create a new dataframe item with the transformed data
        data_state.set_current_table(new_table, name)

    def _after_chat_cleared(self):
        super()._after_chat_cleared()
        self._last_response_id = None
