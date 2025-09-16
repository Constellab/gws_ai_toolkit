from gws_core import BaseModelDTO


class AiTablePlotAgentChatConfig(BaseModelDTO):
    """Configuration class for AI Table with Plot Agent functionality.

    This class extends BaseModelDTO to provide a specialized configuration
    for the AI Table chat system that incorporates a Plot Agent. The Plot
    Agent enables the AI to create interactive Plotly visualizations based on user
    queries about the Excel/CSV data through code generation and execution.

    Unlike plot_file mode, this configuration allows customization of the system
    prompt, model, and temperature settings for flexible data analysis approaches.

    Example:
        config = AiTablePlotAgentChatConfig()
    """
    # OpenAI model to use for chat
    model: str = 'gpt-4o'

    # Temperature for the AI model (0.0 to 2.0)
    temperature: float = 0.7
