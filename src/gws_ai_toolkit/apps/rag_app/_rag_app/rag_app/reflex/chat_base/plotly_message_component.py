import plotly.graph_objects as go
import reflex as rx
from gws_ai_toolkit.models.chat.message.chat_message_plotly import ChatMessagePlotlyFront


class PlotlyFullscreenState(rx.State):
    """State management for Plotly fullscreen dialog.

    Manages the display of Plotly figures in a fullscreen modal dialog,
    allowing users to view charts in a larger format.

    Attributes:
        is_dialog_open: Whether the fullscreen dialog is currently open
        current_figure: The Plotly figure currently displayed in fullscreen
        current_plot_name: Optional name/title of the current plot
    """

    is_dialog_open: bool = False
    # use a dict to avoid errors with go.Figure serialization in Reflex state
    message: dict | None = None

    def open_dialog(self, message: dict):
        """Open the fullscreen dialog with the given figure.

        Args:
            figure: The Plotly figure to display
            plot_name: Optional name/title for the plot
        """
        self.message = message
        self.is_dialog_open = True

    def close_dialog(self):
        """Close the fullscreen dialog and clear the current figure."""
        self.is_dialog_open = False
        self.message = None

    def set_is_dialog_open(self, is_open: bool):
        """Set the dialog open state.

        Args:
            is_open: Whether the dialog should be open
        """
        self.is_dialog_open = is_open


def plotly_fullscreen_dialog() -> rx.Component:
    """Create a fullscreen dialog component to display Plotly figures.

    This dialog displays a Plotly figure in a large modal view, allowing
    users to see charts with more detail and interact with them more easily.

    Returns:
        rx.Component: A dialog component with fullscreen Plotly display
    """
    return rx.dialog.root(
        rx.dialog.content(
            rx.vstack(
                # Header with close button
                rx.hstack(
                    rx.cond(
                        PlotlyFullscreenState.message,
                        rx.dialog.title(
                            PlotlyFullscreenState.message["plot_name"],
                            font_size="18px",
                            font_weight="600",
                        ),
                        rx.dialog.title(
                            "Chart",
                            font_size="18px",
                            font_weight="600",
                        ),
                    ),
                    rx.dialog.close(
                        rx.button(
                            rx.icon("x", size=20),
                            variant="ghost",
                            size="2",
                            on_click=PlotlyFullscreenState.close_dialog,
                        ),
                    ),
                    justify="between",
                    align="center",
                    width="100%",
                    padding_bottom="12px",
                    border_bottom="1px solid var(--gray-6)",
                ),
                # Plotly figure
                rx.box(
                    rx.plotly(
                        data=rx.cond(
                            PlotlyFullscreenState.message["figure"],
                            PlotlyFullscreenState.message["figure"],
                            go.Figure(),
                        ),
                        width="100%",
                        height="100%",
                    ),
                    width="100%",
                    height="70vh",
                    padding="12px 0",
                ),
                spacing="0",
                width="100%",
                height="100%",
            ),
            max_width="95vw",
            max_height="90vh",
            width="95vw",
        ),
        open=PlotlyFullscreenState.is_dialog_open,
        on_open_change=PlotlyFullscreenState.set_is_dialog_open,
    )


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
            rx.vstack(
                # Plotly chart with fullscreen button overlay
                rx.box(
                    rx.plotly(
                        data=rx.cond(message.figure, message.figure, go.Figure()),
                        width="100%",
                    ),
                    # Fullscreen button positioned in top-left corner (hidden by default, shown on parent hover)
                    rx.tooltip(
                        rx.button(
                            rx.icon("expand", size=14),
                            position="absolute",
                            top="2px",
                            left="2px",
                            size="1",
                            variant="soft",
                            on_click=lambda: PlotlyFullscreenState.open_dialog(message),
                            cursor="pointer",
                            background_color="var(--gray-1)",
                            opacity="0",
                            transition="opacity 0.2s ease",
                            class_name="plotly-fullscreen-btn",
                        ),
                        content="Open in fullscreen",
                        side="bottom",
                    ),
                    position="relative",
                    width="100%",
                    class_name="plotly-chart-container",
                    style={
                        "&:hover .plotly-fullscreen-btn": {
                            "opacity": "1",
                        }
                    },
                ),
                spacing="2",
                align_items="center",
                width="100%",
            ),
            width="100%",
        ),
    )
