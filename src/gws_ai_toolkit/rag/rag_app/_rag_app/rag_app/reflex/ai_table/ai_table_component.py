from typing import List

import reflex as rx

from .ai_table_state import AiTableState
from ..chat_base.chat_component import chat_component
from ..chat_base.chat_config import ChatConfig
from ..chat_base.chat_header_component import \
    header_clear_chat_button_component
from ..chat_base.chat_state_base import ChatStateBase


def ai_table_header_default_buttons_component(state: ChatStateBase) -> List[rx.Component]:
    """Default header buttons for the AI Table chat interface.

    Provides standard action buttons for the AI Table page including file viewing
    and chat clearing functionality. These buttons are displayed in the chat header
    and provide quick access to common actions.

    Features:
        - View file button: Opens the current Excel/CSV file being analyzed
        - Clear chat button: Clears the current conversation history

    Args:
        state (ChatStateBase): The current chat state instance for accessing state methods

    Returns:
        List[rx.Component]: List of Reflex button components ready for header display

    Example:
        buttons = ai_table_header_default_buttons_component(ai_table_state)
        # Returns: [view_file_button, clear_chat_button]
    """
    return [
        rx.button(
            rx.icon('table', size=16),
            "View file",
            on_click=lambda: AiTableState.open_current_resource_file,
            variant='outline',
            cursor="pointer",
            size="2",
        ),
        header_clear_chat_button_component(state)
    ]


def ai_table_component(chat_config: ChatConfig | None = None) -> rx.Component:
    """AI Table chat component for Excel/CSV-specific data analysis conversations.

    This component provides a specialized chat interface for having detailed data
    analysis conversations about a specific Excel or CSV file. The AI Table focuses 
    on a single tabular data file and provides comprehensive data analysis, statistical
    insights, and visualizations using OpenAI's code interpreter with pandas.

    Features:
        - Excel/CSV-focused AI conversations with full data analysis capabilities
        - Full file upload mode with code interpreter access
        - Configurable AI models and parameters
        - File viewing and navigation capabilities
        - Persistent conversation history for the specific file
        - Custom header buttons for file-specific actions
        - Data visualization and statistical analysis support

    The component uses AiTableState for state management, which handles:
        - File loading and processing (Excel/CSV only)
        - AI model communication with full file context
        - Configuration management for data analysis
        - Resource management and file metadata

    Args:
        chat_config (ChatConfig | None, optional): Custom ChatConfig to override the defaults.
            If None, creates a default configuration with AiTableState and default header buttons.
            Allows customization of state class and UI components.

    Returns:
        rx.Component: Complete AI Table chat interface with data analysis features,
            header buttons, message display, and input functionality.

    Example:
        # Use with default configuration
        component = ai_table_component()

        # Use with custom configuration
        custom_config = ChatConfig(
            state=AiTableState,
            header_buttons=custom_header_buttons
        )
        component = ai_table_component(custom_config)
    """
    if not chat_config:
        chat_config = ChatConfig(
            state=AiTableState,
            header_buttons=ai_table_header_default_buttons_component
        )

    return chat_component(chat_config)