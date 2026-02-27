import reflex as rx

from .chat_config import ChatConfig
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
    return rx.box(
        rx.vstack(
            chat_messages_list_component(config),
            width="100%",
            padding_bottom="5em",  # Space for fixed input
            flex="1",
            overflow_y="auto",
        ),
        # Fixed input at bottom
        rx.box(
            rx.box(
                chat_input_component(config, hide_border=True),
                # disabled styling when streaming
                background_color=rx.cond(
                    config.state.is_streaming,
                    "var(--gray-2)",
                    "white",
                ),
                border_radius="48px",
                padding_left="12px",
                padding_right="28px",
                box_shadow="0 2px 8px rgba(0, 0, 0, 0.1)",
                max_width="90vw",
                width="100%",
                margin="auto",
            ),
            position="absolute",
            bottom="5px",
            left="50%",
            transform="translateX(-50%)",
            z_index="1000",
            padding="0 20px",
            width="800px",
            max_width="90%",
        ),
        position="relative",
        width="100%",
        height="100%",
        display="flex",
        flex_direction="column",
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
        rx.box(flex="1"),  # Spacer to push input to center
        rx.heading(
            config.state.empty_state_message,
            size="6",
            margin_bottom="1em",
            text_align="center",
            width="100%",
        ),
        rx.box(
            chat_input_component(config),
            width="100%",
            max_width="800px",
            margin="auto",
            class_name="chat",
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
        - Responsive design with mobile-friendly input
        - Empty state messaging
        - Message list display with proper spacing

    Layout Modes:
        - Empty state: Centers input vertically with empty state message
        - With messages: Fixed input at bottom, scrollable message area
        - Three-column: Optional left/right sections (like sources panel)

    Args:
        config (ChatConfig): Configuration object

    Returns:
        rx.Component: Complete chat interface with messages, input, and
            optional side sections, ready for use in any chat application.

    Example:
        config = ChatConfig(
            state=MyChatState,
            sources_component=sources_panel
        )
        chat_ui = chat_component(config)
    """

    # Build children list: optional left section, center chat, optional right section
    children = []

    if config.left_section:
        children.append(
            rx.box(
                config.left_section(config.state),
                flex="none",
                height="100%",
            )
        )

    empty_chat_view = (
        config.empty_chat_component(config) if config.empty_chat_component else _empty_chat(config)
    )

    center_children: list[rx.Component] = []
    if config.header:
        center_children.append(rx.box(config.header, padding_bottom="1em"))

    center_children.append(
        rx.cond(
            # When there are messages, show normal layout with fixed input
            config.state.show_empty_chat,
            # When no messages, center the input vertically
            empty_chat_view,
            # Layout with messages - fixed input at bottom
            _chat_with_messages(config),
        ),
    )

    children.append(
        rx.box(
            *center_children,
            width="100%",
            max_width="800px",
            margin="0 auto",
            position="relative",
            display="flex",
            flex_direction="column",
        )
    )

    if config.right_section:
        children.append(
            rx.box(
                config.right_section(config.state),
                flex="none",
                height="100%",
            )
        )

    return rx.fragment(
        rx.auto_scroll(
            rx.hstack(
                *children,
                align_items="stretch",
                width="100%",
                flex="1",
            ),
            width="100%",
            flex="1",
            display="flex",
            min_height="0",
            on_mount=config.state.on_mount,
        ),
    )
