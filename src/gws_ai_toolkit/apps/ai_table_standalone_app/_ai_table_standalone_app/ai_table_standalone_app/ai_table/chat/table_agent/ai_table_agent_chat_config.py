from gws_core import BaseModelDTO


class AiTableAgentChatConfig(BaseModelDTO):
    """Configuration class for AI Table with unified Table Agent functionality.

    This class extends BaseModelDTO to provide a specialized configuration
    for the AI Table chat system that incorporates a unified Table Agent. The Table
    Agent intelligently routes requests to either PlotlyAgentAi for data visualization
    or TableTransformAgentAi for data transformation using OpenAI function calling.

    The agent automatically determines the appropriate operation type (plotting vs transformation)
    based on user queries and delegates to the specialized sub-agents accordingly.

    Key Features:
        - Unified interface for both plotting and transformation operations
        - Intelligent request routing via function calling
        - Configurable OpenAI model and temperature settings
        - Seamless integration with existing specialized agents

    Example:
        config = AiTableTableAgentChatConfig()
        # Uses default GPT-4o model with 0.7 temperature for balanced creativity/accuracy
    """

    # OpenAI model to use for chat
    model: str = "gpt-4o"

    # Temperature for the AI model (0.0 to 2.0)
    # Lower values (0.1-0.3) for more deterministic function calling
    # Higher values (0.7-1.0) for more creative responses
    temperature: float = 0.3

    # Enable save functionality for the chat conversation
    # When True, displays a save button allowing users to save the chat and replay it
    enable_chat_save: bool = False
