from typing import Optional

import pandas as pd
import reflex as rx

from gws_ai_toolkit._app.chat_base import OpenAiChatStateBase
from gws_ai_toolkit.core.agents.plotly_agent_ai import (PlotlyAgentAi,
                                                        PlotlyAgentAiDTO)
from gws_ai_toolkit.core.agents.plotly_agent_ai_events import PlotlyAgentEvent

from ...ai_table_data_state import AiTableDataState
from .ai_table_plot_agent_chat_config import AiTablePlotAgentChatConfig
from .ai_table_plot_agent_chat_config_state import \
    AiTablePlotAgentChatConfigState


class AiTablePlotAgentChatState(OpenAiChatStateBase, rx.State):
    """State management for AI Table Chat - specialized Excel/CSV-focused chat functionality.

    This state class manages the AI Table chat workflow, providing intelligent
    data analysis capabilities focused on a specific Excel or CSV file. It integrates
    with OpenAI's API to provide data analysis, statistical insights, and interactive
    exploration of tabular data using generated Python code execution.

    Key Features:
        - Excel/CSV-specific chat with data analysis capabilities
        - Table metadata sharing (column names, types, row count) instead of file upload
        - OpenAI integration with streaming responses and function calling
        - Dynamic code generation and execution for data visualization
        - Conversation history persistence
        - Error handling and user feedback

    Processing Mode:
        - Metadata-only mode: Shares table structure and metadata with OpenAI
        - Code generation: OpenAI generates Python code for Plotly visualizations
        - Local execution: Generated code is executed locally with the actual DataFrame

    Inherits from BaseFileAnalysisState providing:
        - File loading and validation
        - OpenAI integration with streaming responses
        - Conversation history integration
        - Error handling and user feedback
    """

    # UI configuration
    title = "AI Table Analyst"
    placeholder_text = "Ask about this Excel/CSV data..."
    empty_state_message = "Start analyzing your Excel/CSV data"

    _plotly_agent_dto: Optional[PlotlyAgentAiDTO] = None

    ANALYSIS_TYPE = "ai_table"

    async def call_ai_chat(self, user_message: str) -> None:
        """Get streaming response from OpenAI about the table data using PlotAgentService"""

        plotly_agent = await self._get_plotly_agent()

        # Stream plot generation events
        for event in plotly_agent.call_agent(
            user_query=user_message,
        ):
            await self._handle_plot_agent_event(event)

        async with self:
            # Save the PlotlyAgentAi state for continuity in future interactions
            self._plotly_agent_dto = plotly_agent.to_dto()

    async def _handle_plot_agent_event(self, event: PlotlyAgentEvent) -> None:
        """Handle events from the plot agent service"""
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
        config: AiTablePlotAgentChatConfig
        async with self:
            config = await self._get_config()

        # Save conversation to history after response is completed
        await self.save_conversation_to_history(self.ANALYSIS_TYPE, config.to_json_dict())

    async def _get_plotly_agent(self) -> PlotlyAgentAi:
        """Get or create PlotlyAgentAi instance"""
        async with self:
            openai_client = self._get_openai_client()

            # Get required data
            dataframe = await self._get_active_dataframe()
            if dataframe is None:
                raise ValueError("No active dataframe available for analysis")

            if self._plotly_agent_dto:
                return PlotlyAgentAi.from_dto(
                    dto=self._plotly_agent_dto,
                    openai_client=openai_client,
                    dataframe=dataframe,
                )
            else:
                config = await self._get_config()
                return PlotlyAgentAi(
                    openai_client=openai_client,
                    dataframe=dataframe,
                    model=config.model,
                    temperature=config.temperature
                )

    async def _get_config(self) -> AiTablePlotAgentChatConfig:
        """Get configuration for AI Table analysis

        Returns:
            AiTablePlotAgentChatConfig: Configuration object for AI Table
        """
        app_config_state = await self.get_state(AiTablePlotAgentChatConfigState)
        config = await app_config_state.get_config()
        return config

    # Prompt creation now handled by PlotAgentService

    async def _get_active_dataframe(self) -> Optional[pd.DataFrame]:
        """Get the active DataFrame for the currently active table (original or subtable)"""
        data_state: AiTableDataState = await self.get_state(AiTableDataState)

        dataframe_item = data_state.get_current_dataframe_item()
        if not dataframe_item:
            return None
        return dataframe_item.get_dataframe()

    def _after_chat_cleared(self):
        super()._after_chat_cleared()
        self._plotly_agent_dto = None
