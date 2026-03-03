import reflex as rx
from gws_ai_toolkit.models.chat.message.chat_message_plotly import ChatMessagePlotlyFront
from gws_reflex_base import plotly_with_fullscreen


def plotly_message_component(message: ChatMessagePlotlyFront) -> rx.Component:
    """Renders plotly figure content with fullscreen button.

    Args:
        message (ChatMessagePlotlyFront): Plotly message to render

    Returns:
        rx.Component: Plotly figure display with fullscreen button overlay
    """
    return rx.cond(
        message.figure,
        rx.box(
            plotly_with_fullscreen(
                figure=message.figure,
                plot_name=message.plot_name,
            ),
            width="100%",
        ),
    )
