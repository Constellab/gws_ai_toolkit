import reflex as rx
from gws_ai_toolkit._app.ai_chat import ConversationChatStateBase
from gws_ai_toolkit.models.chat.conversation.ai_table_agent_chat_conversation import (
    AiTableAgentChatConfig,
    AiTableAgentChatConversation,
)
from gws_ai_toolkit.models.chat.conversation.base_chat_conversation import (
    BaseChatConversation,
    BaseChatConversationConfig,
)
from gws_ai_toolkit.models.chat.message import ChatMessageDataframe
from gws_ai_toolkit.models.chat.message.chat_message_base import ChatMessageBase
from gws_core.impl.table.table import Table
from gws_reflex_main import ReflexMainState

from ...ai_table_data_state import AiTableDataState
from .ai_table_agent_chat_config_state import AiTableAgentChatConfigState


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

    async def create_conversation(self) -> BaseChatConversation:
        """Create a new AiTableAgentChatConversation instance.

        Gets the current table from AiTableDataState and configuration from
        AiTableAgentChatConfigState to create a properly configured conversation.

        Returns:
            BaseChatConversation: A new AiTableAgentChatConversation configured with
                the current table and config.
        """
        # Get current table
        data_state = await self.get_state(AiTableDataState)
        table = data_state.get_current_table()

        if table is None:
            raise ValueError("No active table available for analysis")

        table_name = data_state.current_table_name

        # Get config
        app_config_state = await self.get_state(AiTableAgentChatConfigState)
        config: AiTableAgentChatConfig = await app_config_state.get_config()

        main_state = await self.get_state(ReflexMainState)
        user = await main_state.get_current_user()

        conv_config = BaseChatConversationConfig(
            "ai_table_unified", store_conversation_in_db=False, user=user.to_dto() if user else None
        )

        return AiTableAgentChatConversation(
            config=conv_config,
            chat_configuration=config,
            table=table,
            table_name=table_name,
        )

    async def configure_conversation_before_message(self, conversation: BaseChatConversation) -> None:
        return await super().configure_conversation_before_message(conversation)

    async def _after_message_added(self, message: ChatMessageBase):
        if isinstance(message, ChatMessageDataframe) and message.dataframe is not None:
            # Update the current table in AiTableDataState when a dataframe message is added
            async with self:
                data_state = await self.get_state(AiTableDataState)
                data_state.add_table(
                    Table(message.dataframe), message.dataframe_name or "transformed_table", id_=message.id
                )
