import reflex as rx

from .chat_config import ChatConfig
from .chat_header_component import chat_header_component
from .chat_input_component import chat_input_component
from .messages_list_component import chat_messages_list_component


def _chat_with_messages(config: ChatConfig) -> rx.Component:
    """Chat layout when messages are present - fixed input at bottom.
    
    This layout is used when the chat has messages to display. It provides
    a scrollable message area with a fixed input field at the bottom of
    the screen for easy access.
    
    Args:
        config (ChatConfig): Chat configuration with state and components
        
    Returns:
        rx.Component: Layout with scrollable messages and fixed bottom input
    """
    return rx.fragment(
        rx.vstack(
            chat_header_component(config),
            chat_messages_list_component(config),
            width="100%",
            max_width="800px",
            margin="auto",
            padding="1em 1em 5em 1em",
            flex="1",
        ),
        # Fixed input at bottom
        rx.box(
            rx.box(
                chat_input_component(config),
                background_color="white",
                border_radius="48px",
                padding="12px 28px 12px 24px",
                box_shadow="0 2px 8px rgba(0, 0, 0, 0.1)",
                max_width="90vw",
                width="100%",
                margin="auto",
            ),
            position="fixed",
            bottom="20px",
            left="50%",
            transform="translateX(-50%)",
            z_index="1000",
            padding="0 20px",
            width="800px",
        )
    )


def _empty_chat(config: ChatConfig) -> rx.Component:
    """Chat layout for empty state - centered input with welcome message.
    
    This layout is used when the chat has no messages. It centers the input
    field vertically and displays a welcome message to guide the user.
    
    Args:
        config (ChatConfig): Chat configuration with state and components
        
    Returns:
        rx.Component: Centered layout with empty state message and input
    """
    return rx.vstack(
        chat_header_component(config),
        rx.box(flex="1"),  # Spacer to push input to center
        rx.heading(
            config.state.empty_state_message,
            size="6",
            margin_bottom="1em",
            text_align="center",
            width="100%"
        ),
        rx.box(
            chat_input_component(config),
            width="100%",
            max_width="800px",
            margin="auto",

            class_name="chat"
        ),
        rx.box(flex="2"),  # Spacer to center input
        width="100%",
        flex="1",
    )


def chat_component(config: ChatConfig) -> rx.Component:
    """Universal chat interface component providing complete chat functionality.
    
    This is the core chat component that provides a full-featured chat interface
    with adaptive layout, message display, input handling, and customizable sections.
    It automatically adapts its layout based on whether messages are present and
    provides a consistent user experience across different chat implementations.
    
    Features:
        - Adaptive layout (centered input when empty, fixed input when messages exist)
        - Three-column layout with customizable left/right sections
        - Auto-scrolling message area
        - Configurable header with custom buttons
        - Responsive design with mobile-friendly input
        - Empty state messaging
        - Message list display with proper spacing
        
    Layout Modes:
        - Empty state: Centers input vertically with empty state message
        - With messages: Fixed input at bottom, scrollable message area
        - Three-column: Optional left/right sections (like sources panel)
        
    Args:
        config (ChatConfig): Configuration object containing:
            - state: ChatStateBase instance for state management
            - header_buttons: Optional custom header buttons
            - sources_component: Optional component for displaying sources
            - left_section: Optional left sidebar component
            - right_section: Optional right sidebar component

    Returns:
        rx.Component: Complete chat interface with header, messages, input, and
            optional side sections, ready for use in any chat application.
            
    Example:
        config = ChatConfig(
            state=MyChatState,
            header_buttons=custom_buttons,
            sources_component=sources_panel
        )
        chat_ui = chat_component(config)
    """

    return rx.auto_scroll(
        rx.hstack(
            rx.box(config.left_section, flex="1", height="100%"),
            rx.box(
                rx.cond(
                    # When there are messages, show normal layout with fixed input
                    config.state.messages_to_display,
                    # Layout with messages - fixed input at bottom
                    _chat_with_messages(config),
                    # When no messages, center the input vertically
                    _empty_chat(config)
                ),
                width="100%",
                max_width="800px",
                position="relative",
                display="flex",
                flex_direction="column"
            ),
            rx.box(config.right_section, flex="1", height="100%"),
            align_items="stretch",
            justify_content="stretch",
            width="100%",
        ),
        width="100%",
        flex="1",
        display="flex",
        min_height="0",
    )
