import os
from dataclasses import dataclass

import reflex as rx
from gws_ai_toolkit._app.ai_chat import ConversationChatStateBase
from gws_ai_toolkit.core.agents.table_agent_ai import TableAgentAi
from gws_ai_toolkit.core.excel_file import ExcelSheetDTO
from gws_ai_toolkit.models.chat.conversation.ai_table_agent_chat_conversation import (
    AiTableAgentChatConversation,
)
from gws_ai_toolkit.models.chat.conversation.base_chat_conversation import (
    BaseChatConversation,
    BaseChatConversationConfig,
)
from gws_ai_toolkit.models.chat.message.chat_message_base import ChatMessageBase
from gws_ai_toolkit.models.chat.message.chat_message_dataframe import ChatMessageDataframe
from gws_core.impl.table.table import Table
from gws_reflex_main import ReflexMainState

from ...ai_table_data_state import AiTableDataState
from .ai_table_agent_chat_config import AiTableAgentChatConfig
from .ai_table_agent_chat_config_state import AiTableAgentChatConfigState


@dataclass
class SelectedTableDTO:
    id: str
    name: str
    sheet_name: str | None
    unique_name: str


class AiTableAgentChatState(ConversationChatStateBase, rx.State):
    """State management for AI Table Agent Chat - unified table operations functionality.

    This state class manages the AI Table Agent chat workflow using the new
    ConversationChatStateBase and AiTableAgentChatConversation architecture.
    It provides intelligent routing between data visualization and transformation
    capabilities through OpenAI function calling.

    Key Features:
        - Unified interface for both plotting and transformation operations
        - Intelligent request routing using OpenAI function calling
        - Automatic delegation to PlotlyAgentAi and TableTransformAgentAi
        - Seamless context preservation across different operation types
        - Real-time table updates from transformation operations
        - Automatic conversation persistence

    The state connects to the TableAgentAi and processes user queries
    by intelligently routing to either visualization or transformation agents.
    """

    # UI configuration
    title: str = "AI Table Operations"
    placeholder_text: str = "Ask me to visualize or transform your data..."
    empty_state_message: str = "Start with data visualization or transformation requests"

    _selected_tables: list[ExcelSheetDTO]

    async def on_load(self):
        if not self._conversation:
            self._selected_tables = []
            data_state = await self.get_state(AiTableDataState)
            table = data_state.get_current_table()
            if table is not None:
                self._selected_tables.append(table)

    async def _create_conversation(self) -> BaseChatConversation:
        """Create a new AiTableAgentChatConversation instance.

        Gets the current table from AiTableDataState and configuration from
        AiTableAgentChatConfigState to create a properly configured conversation.

        Returns:
            BaseChatConversation: A new AiTableAgentChatConversation configured with
                the current table and config.
        """

        if not self._selected_tables:
            raise ValueError("No selected tables available for conversation, please select a table.")

        # Get config
        app_config_state = await self.get_state(AiTableAgentChatConfigState)
        config: AiTableAgentChatConfig = await app_config_state.get_config()

        # Get OpenAI API key
        api_key = self._get_openai_api_key()

        # Create TableAgentAi with API key
        table_agent = TableAgentAi(
            openai_api_key=api_key,
            model=config.model,
            temperature=config.temperature,
        )

        main_state = await self.get_state(ReflexMainState)
        user = await main_state.get_current_user()

        conv_config = BaseChatConversationConfig(
            "ai_table_unified", store_conversation_in_db=False, user=user.to_dto() if user else None
        )

        return AiTableAgentChatConversation(
            config=conv_config,
            table_agent=table_agent,
        )

    def _get_openai_api_key(self) -> str:
        """Get OpenAI API key from environment."""
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise ValueError("OpenAI API key is not set")
        return api_key

    async def configure_conversation_before_message(self, conversation: BaseChatConversation) -> None:
        if isinstance(conversation, AiTableAgentChatConversation):
            # Update tables in the conversation before processing a new message
            conversation.table_agent.clear_tables()
            for table_dto in self._selected_tables:
                conversation.table_agent.add_table(table_dto.get_unique_name(), table_dto.table)

    async def _after_message_added(self, message: ChatMessageBase):
        if isinstance(message, ChatMessageDataframe) and message.dataframe is not None:
            # Update the current table in AiTableDataState when a dataframe message is added
            async with self:
                data_state = await self.get_state(AiTableDataState)
                table_dto = data_state.add_table(
                    Table(message.dataframe), message.dataframe_name or "transformed_table", id_=message.id
                )
                self._selected_tables = [table_dto]  # Set the new table as the only selected table

    @rx.var
    def selected_tables(self) -> list[SelectedTableDTO]:
        """Get the current tables available in the chat state.

        Returns:
            dict[str, Table]: Dictionary of current tables by their IDs.
        """
        return [
            SelectedTableDTO(
                id=table.id,
                name=table.name,
                sheet_name=table.sheet_name,
                unique_name=table.name + (f" > {table.sheet_name}" if table.sheet_name else ""),
            )
            for table in self._selected_tables
        ]

    @rx.var
    async def current_table_ssuggestion(self) -> SelectedTableDTO | None:
        """Return the currently selected table as a selectable item if not already selected.

        This is used to show the current table in the selectable list if not already selected,
        to make selection easier.
        """
        data_state = await self.get_state(AiTableDataState)
        current_table = data_state.get_current_table()
        if current_table is None:
            return None

        # if table not the selected tables, return it
        if not self._table_is_selected(current_table.id, current_table.sheet_name):
            return SelectedTableDTO(
                id=current_table.id,
                name=current_table.name,
                sheet_name=current_table.sheet_name,
                unique_name=current_table.name + (f" > {current_table.sheet_name}" if current_table.sheet_name else ""),
            )

    @rx.event
    def remove_table(self, table: SelectedTableDTO):
        """Remove a table from the current tables by id and sheet name."""

        self._selected_tables = [
            t for t in self._selected_tables if not (t.id == table.id and t.sheet_name == table.sheet_name)
        ]

    @rx.event
    async def add_table(self, table_id: str, sheet_name: str):
        """Add a table to the current tables by ID and sheet name.

        Args:
            table_id (str): The ID of the table to add.
            sheet_name (str): The sheet name of the table to add.
        """
        # check if already added
        if self._table_is_selected(table_id, sheet_name):
            return
        data_state = await self.get_state(AiTableDataState)
        table = data_state.get_table(table_id, sheet_name)
        if table:
            self._selected_tables.append(table)

    def _table_is_selected(self, table_id: str, sheet_name: str | None) -> bool:
        """Check if a table is already selected.

        Args:
            table_id (str): The ID of the table to check.
            sheet_name (str): The sheet name of the table to check.
        Returns:
            bool: True if the table is selected, False otherwise.
        """
        return any(t.id == table_id and t.sheet_name == sheet_name for t in self._selected_tables)
