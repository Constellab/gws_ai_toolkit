import reflex as rx

from ..ai_table_data_state import AiTableDataState
from .plot_agent.ai_table_plot_agent_chat_component import \
    ai_table_plot_agent_chat_component
from .table_agent.ai_table_table_agent_chat_component import \
    ai_table_table_agent_chat_component
from .transform_agent.ai_table_transform_agent_chat_component import \
    ai_table_transform_agent_chat_component


def _chat_mode_selector():
    """Chat mode selector component"""
    return rx.hstack(
        rx.text("Mode:", font_weight="bold"),
        rx.select.root(
            rx.select.trigger(
                placeholder="Select chat mode",
            ),
            rx.select.content(
                rx.select.item(
                    "📊 Plot & Visualize",
                    value="plot",
                ),
                rx.select.item(
                    "🔧 Transform Data",
                    value="transform",
                ),
            ),
            value=AiTableDataState.current_chat_mode,
            on_change=AiTableDataState.set_chat_mode,
        ),
        spacing="2",
        align="center",
        margin_bottom="0.5em"
    )


def ai_table_unified_chat_component():
    """Unified chat component that switches between different AI agents.

    This component provides a unified interface for different AI chat modes:
    - Plot Mode: AI Plot Agent for creating visualizations
    - Transform Mode: AI Transform Agent for data transformation

    Features:
        - Mode selector to switch between different AI agents
        - Seamless switching with preserved conversation context
        - Unified interface for all data analysis tasks

    Returns:
        rx.Component: Complete unified chat interface with mode switching
    """
    return rx.vstack(
        # Chat mode selector
        # _chat_mode_selector(),

        # Chat component based on current mode
        ai_table_table_agent_chat_component(),

        width="100%",
        height="100%",
        flex="1",
        display="flex",
        flex_direction="column",
        spacing="0",
    )
