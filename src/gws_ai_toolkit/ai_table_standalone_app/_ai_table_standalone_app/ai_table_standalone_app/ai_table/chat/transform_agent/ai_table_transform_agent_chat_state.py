from typing import Optional

import pandas as pd
import reflex as rx

from gws_ai_toolkit._app.chat_base import OpenAiChatStateBase
from gws_ai_toolkit.core.agents.dataframe_transform_agent_ai import (
    DataFrameTransformAgentAi, DataFrameTransformAgentAiDTO)
from gws_ai_toolkit.core.agents.dataframe_transform_agent_ai_events import \
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

    _transform_agent_dto: Optional[DataFrameTransformAgentAiDTO] = None

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
            self._transform_agent_dto = transform_agent.to_dto()

    async def _handle_transform_agent_event(self, event: DataFrameTransformAgentEvent) -> None:
        """Handle events from the transform agent service"""
        if event.type == "text_delta":
            await self.handle_output_text_delta(event.delta)
        elif event.type == "dataframe_transform":
            # Handle successful DataFrame transformation
            transformed_df = event.dataframe
            response_id = event.response_id

            async with self:
                # Update the active DataFrame with the transformed version
                await self._update_active_dataframe(transformed_df)

                # Create a message showing the transformation result
                message = self.create_text_message(
                    content=f"✅ DataFrame transformed successfully!\n\nNew shape: {transformed_df.shape[0]} rows × {transformed_df.shape[1]} columns\n\nTransformation code:\n```python\n{event.code}\n```",
                    role="assistant",
                    external_id=response_id
                )
            await self.update_current_response_message(message)
        elif event.type == "error":
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

    async def _get_transform_agent(self) -> DataFrameTransformAgentAi:
        """Get or create DataFrameTransformAgentAi instance"""
        async with self:
            openai_client = self._get_openai_client()

            # Get required data
            dataframe = await self._get_active_dataframe()
            if dataframe is None:
                raise ValueError("No active dataframe available for transformation")

            if self._transform_agent_dto:
                return DataFrameTransformAgentAi.from_dto(
                    dto=self._transform_agent_dto,
                    openai_client=openai_client,
                    dataframe=dataframe,
                )
            else:
                config = await self._get_config()
                return DataFrameTransformAgentAi(
                    openai_client=openai_client,
                    dataframe=dataframe,
                    model=config.model,
                    temperature=config.temperature
                )

    async def _get_config(self) -> AiTableTransformAgentChatConfig:
        """Get configuration for AI Table Transform Agent analysis

        Returns:
            AiTableTransformAgentChatConfig: Configuration object for AI Table Transform Agent
        """
        app_config_state = await self.get_state(AiTableTransformAgentChatConfigState)
        config = await app_config_state.get_config()
        return config

    async def _get_active_dataframe(self) -> Optional[pd.DataFrame]:
        """Get the active DataFrame for the currently active table (original or subtable)"""
        data_state: AiTableDataState = await self.get_state(AiTableDataState)

        dataframe_item = data_state.get_current_dataframe_item()
        if not dataframe_item:
            return None
        return dataframe_item.get_dataframe()

    async def _update_active_dataframe(self, new_dataframe: pd.DataFrame) -> None:
        """Update the active DataFrame with a transformed version"""
        data_state: AiTableDataState = await self.get_state(AiTableDataState)

        # Create a new dataframe item with the transformed data
        await data_state.set_transformed_dataframe(new_dataframe)

    def _after_chat_cleared(self):
        super()._after_chat_cleared()
        self._transform_agent_dto = None
