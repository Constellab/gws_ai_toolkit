from gws_core import BaseModelDTO


class AiTableTransformAgentChatConfig(BaseModelDTO):
    """Configuration class for AI Table with Transform Agent functionality.

    This class extends BaseModelDTO to provide a specialized configuration
    for the AI Table chat system that incorporates a Transform Agent. The Transform
    Agent enables the AI to clean, transform, and manipulate DataFrame data based on user
    queries about the Excel/CSV data through code generation and execution.

    The agent can perform operations like:
    - Data cleaning (removing duplicates, handling missing values)
    - Column operations (adding, removing, renaming, reordering)
    - Row operations (filtering, sorting, grouping, aggregation)
    - Data reshaping (pivot, melt, merge, join)
    - String and date/time operations

    Example:
        config = AiTableTransformAgentChatConfig()
    """
    # OpenAI model to use for chat
    model: str = 'gpt-4o'

    # Temperature for the AI model (0.0 to 2.0)
    temperature: float = 0.7