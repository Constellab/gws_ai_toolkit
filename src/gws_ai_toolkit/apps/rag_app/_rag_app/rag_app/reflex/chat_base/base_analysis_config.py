from abc import ABC
from gws_core import BaseModelDTO


class BaseAnalysisConfig(BaseModelDTO, ABC):
    """Base configuration class for AI analysis functionality.

    This class defines common configurable parameters for AI analysis systems,
    including AI model settings and system prompts. It extends BaseModelDTO to
    provide serialization and validation capabilities.

    All analysis types (Expert, Table, etc.) share these common parameters,
    while specific analysis types can extend this with their own parameters.

    Attributes:
        prompt_file_placeholder (str): Placeholder token used in system prompt to represent
            the file name/identifier. Default: "[FILE]"

        system_prompt (str): The system prompt template that instructs the AI how to
            behave when analyzing files. Should include the prompt_file_placeholder.
            Must be overridden by subclasses.

        model (str): OpenAI model identifier to use for chat responses.
            Default: 'gpt-4o'

        temperature (float): AI model temperature controlling response randomness.
            Range: 0.0 (focused) to 2.0 (creative), Default: 0.7

    Example:
        class MyAnalysisConfig(BaseAnalysisConfig):
            system_prompt: str = "You are an AI specialized in..."
    """

    prompt_file_placeholder: str = "[FILE]"

    # Abstract - must be overridden by subclasses
    system_prompt: str = ""

    # OpenAI model to use for chat
    model: str = "gpt-4o"

    # Temperature for the AI model (0.0 to 2.0)
    temperature: float = 0.7
