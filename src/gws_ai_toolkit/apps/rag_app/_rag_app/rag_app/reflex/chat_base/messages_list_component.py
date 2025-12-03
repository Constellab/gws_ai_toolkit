import plotly.graph_objects as go
import reflex as rx
from gws_ai_toolkit.apps.rag_app._rag_app.rag_app.reflex.chat_base.sources_list_component import (
    SourcesComponentBuilder,
    sources_list_component,
)
from gws_ai_toolkit.models.chat.message.chat_message_code import ChatMessageCode
from gws_ai_toolkit.models.chat.message.chat_message_error import ChatMessageError
from gws_ai_toolkit.models.chat.message.chat_message_hint import ChatMessageHint
from gws_ai_toolkit.models.chat.message.chat_message_image import ChatMessageImage
from gws_ai_toolkit.models.chat.message.chat_message_plotly import ChatMessagePlotlyFront
from gws_ai_toolkit.models.chat.message.chat_message_source import ChatMessageSource
from gws_ai_toolkit.models.chat.message.chat_message_streaming import ChatMessageStreaming
from gws_ai_toolkit.models.chat.message.chat_message_text import ChatMessageText
from gws_ai_toolkit.models.chat.message.chat_message_types import ChatMessage
from gws_ai_toolkit.models.chat.message.chat_user_message import ChatUserMessageBase, ChatUserMessageText
from gws_reflex_main import user_profile_picture

from .chat_config import ChatConfig
from .conversation_chat_state_base import ConversationChatStateBase


def _message_bubble(message: ChatMessage, config: ChatConfig) -> rx.Component:
    """Individual message bubble component with role-based styling.

    Creates styled message bubbles with different appearances for user and
    assistant messages. Handles content rendering, source display, and
    responsive layout.

    Args:
        message (ChatMessageFront): The message to render
        config (ChatConfig): Chat configuration for styling and components

    Returns:
        rx.Component: Styled message bubble with appropriate alignment and content
    """

    return rx.box(
        _message_component(message, config),
        padding="12px 0",
        word_wrap="break-word",
        width="100%",
    )


def _streaming_indicator(state_class: ConversationChatStateBase) -> rx.Component:
    """Loading indicator shown during AI response streaming.

    Displays a spinner and "thinking" message when the AI is generating
    a response, providing visual feedback to the user.

    Args:
        state_class (ConversationChatStateBase): Chat state to check streaming status

    Returns:
        rx.Component: Conditional loading indicator based on streaming state
    """
    return rx.cond(
        state_class.is_streaming,
        rx.box(
            rx.hstack(
                rx.spinner(),
                rx.text("Assistant is thinking...", font_style="italic", color="gray.600"),
                spacing="2",
            ),
            margin="0.5em 0",
            width="100%",
            align_items="center",
        ),
        rx.text(""),
    )


def chat_messages_list_component(config: ChatConfig) -> rx.Component:
    """Complete message display component for chat interfaces.

    This component renders the complete message list for chat interfaces, handling
    different message types (text, image, code), streaming indicators, and proper
    layout with user/assistant message styling. It provides the core message
    display functionality used across all chat implementations.

    Features:
        - Multi-type message rendering (text, image, code)
        - Distinct styling for user vs assistant messages
        - Real-time streaming message display
        - Source citations and references
        - Proper spacing and responsive layout
        - Loading indicators during AI responses
        - Empty state message when no messages exist

    Args:
        config (ChatConfig): Chat configuration containing:
            - state: Provides messages and streaming state
            - sources_component: Optional component for displaying sources

    Returns:
        rx.Component: Complete scrollable message list with all message types,
            streaming indicators, and proper styling for chat display.

    Example:
        messages = chat_messages_list_component(chat_config)
        # Renders all messages with proper styling and streaming support
    """

    return rx.box(
        # Show empty state message when no messages exist
        rx.cond(
            config.state.show_empty_chat,
            rx.box(
                rx.text(
                    config.state.empty_state_message
                    if hasattr(config.state, "empty_state_message")
                    else "Start a conversation...",
                    color="var(--gray-9)",
                    font_size="16px",
                    text_align="center",
                ),
                display="flex",
                align_items="center",
                justify_content="center",
                height="100%",
                width="100%",
            ),
            rx.box(
                rx.foreach(config.state.chat_messages, lambda message: _message_bubble(message, config)),
                # Display current response message separately
                rx.cond(
                    config.state.current_response_message,
                    _message_bubble(config.state.current_response_message, config),
                    rx.text(""),
                ),
                _streaming_indicator(config.state),
                width="100%",
            ),
        ),
        width="100%",
        padding="1em",
        flex="1",
    )


def _message_component(message: ChatMessage, config: ChatConfig) -> rx.Component:  # type: ignore
    """Content renderer that handles different message types.

    Routes message content to appropriate rendering functions based on
    message type (text, image, code), ensuring proper display formatting.

    Args:
        message (ChatMessage): Message with type-specific content
        config (ChatConfig): Chat configuration for custom message renderers
    Returns:
        rx.Component: Rendered content appropriate for the message type
    """

    # Default renderers for each type
    default_renderers = {
        "text": _text_content,
        "streaming-text": _text_content,
        "user-text": user_message_base,
        "image": _image_content,
        "code": _code_content,
        "plotly": _plotly_content,
        "error": _error_content,
        "hint": _hint_content,
    }

    # Build match cases: custom renderers take priority, then defaults
    renderers = {}
    if config.custom_chat_messages:
        renderers.update(config.custom_chat_messages)

    # Add default renderers for types not in custom
    for msg_type, default_renderer in default_renderers.items():
        if msg_type not in renderers:
            renderers[msg_type] = default_renderer

    # Build the match cases
    match_cases = [(msg_type, renderer(message)) for msg_type, renderer in renderers.items()]

    return rx.match(  # type: ignore
        message.type,  # type: ignore
        *match_cases,  # type: ignore
        rx.text(f"Unsupported message type {message.type}."),  # type: ignore
    )


def _text_content(message: ChatMessageText | ChatUserMessageText | ChatMessageStreaming) -> rx.Component:
    """Renders text content with markdown support.

    Args:
        message (ChatMessageText): Text message to render

    Returns:
        rx.Component: Markdown-rendered text content
    """
    return _message_content(message.content)


def _message_content(content: str) -> rx.Component:
    """Renders text content with markdown support.

    Args:
        message (ChatMessageText): Text message to render

    Returns:
        rx.Component: Markdown-rendered text content
    """
    return rx.markdown(
        content,
        font_size="14px",
    )


def user_message_base(message: ChatUserMessageBase) -> rx.Component:
    """Renders text content with markdown support.

    Args:
        message (ChatMessageText): Text message to render

    Returns:
        rx.Component: Markdown-rendered text content
    """
    return rx.hstack(
        rx.box(
            _message_content(message.content),
            background_color="var(--accent-10)",
            padding="0px 16px",
            border_radius="18px",
            max_width="70%",
            word_wrap="break-word",
            color="white",
        ),
        rx.cond(
            message.user,
            user_profile_picture(message.user, size="normal"),
            rx.box(),
        ),
        spacing="2",
        align_items="flex-start",
        justify="end",
        width="100%",
    )


def message_source(
    message: ChatMessageSource,
    state: ConversationChatStateBase,
    sources_component: SourcesComponentBuilder | None = None,
) -> rx.Component:
    return rx.box(
        _message_content(message.content),
        rx.cond(
            message.sources,
            rx.box(
                sources_component(message.sources, state)
                if sources_component
                else sources_list_component(message.sources, state)
            ),
        ),
    )


def _image_content(message: ChatMessageImage) -> rx.Component:
    """Renders image content with optional text description.

    Args:
        message (ChatMessageImage) -> rx.Component:
    """
    return rx.image(
        src=message.image,  # Use image_path instead of data
        max_width="100%",
        height="auto",
    )


def _code_content(message: ChatMessageCode) -> rx.Component:
    """Renders code content with syntax highlighting.

    Args:
        message (ChatMessageCode): Code message to render

    Returns:
        rx.Component: Syntax-highlighted code block
    """
    return rx.code_block(
        code=rx.cond(message.code, message.code, ""),
        language="python",
        border_radius="8px",
        padding="1em",
    )


def _plotly_content(message: ChatMessagePlotlyFront) -> rx.Component:
    """Renders plotly figure content.

    Args:
        message (ChatMessagePlotlyFront): Plotly message to render

    Returns:
        rx.Component: Plotly figure display with optional plot name
    """
    return rx.cond(
        message.figure,
        rx.vstack(
            rx.plotly(
                # rx.cond used to avoid warning
                data=rx.cond(message.figure, message.figure, go.Figure()),
                width="100%",
            ),
            # rx.cond(
            #     message.plot_name,
            #     rx.text(
            #         message.plot_name,
            #         font_weight="500",
            #         font_size="14px",
            #         color="var(--gray-11)",
            #         margin_top="8px",
            #         text_align="center",
            #     ),
            # ),
            spacing="2",
            align_items="center",
            width="100%",
        ),
    )


def _error_content(message: ChatMessageError) -> rx.Component:
    """Renders error content with distinctive error styling.

    Args:
        message (ChatMessageError): Error message to render

    Returns:
        rx.Component: Error content with red background and warning styling
    """
    return rx.box(
        rx.hstack(
            rx.icon("triangle-alert", size=16, color="red", flex_shrink="0"),
            rx.text(
                message.error,
                font_size="14px",
                color="red",
            ),
            spacing="2",
            align_items="center",
        ),
        background_color="rgba(239, 68, 68, 0.1)",
        border_left="4px solid red",
        padding="12px",
        border_radius="8px",
    )


def _hint_content(message: ChatMessageHint) -> rx.Component:
    """Renders hint content with distinctive hint styling.

    Args:
        message (ChatMessageHint): Hint message to render

    Returns:
        rx.Component: Hint content with blue background and lightbulb icon
    """
    return rx.box(
        rx.hstack(
            rx.icon("lightbulb", size=16, color="var(--accent-9)"),
            rx.text(
                message.content,
                font_size="14px",
                color="var(--accent-11)",
            ),
            spacing="2",
            align_items="center",
        ),
        background_color="var(--accent-3)",
        border_left="4px solid var(--accent-9)",
        padding="12px",
        border_radius="8px",
    )
