from typing import Any, ClassVar, Literal, get_args

from gws_core import BaseModelDTO, Logger
from pydantic import field_validator

AiExpertChatMode = Literal["full_text_chunk", "relevant_chunks"]

# Selectable modes, in the order they are displayed in the configuration form
AI_EXPERT_CHAT_MODES: list[AiExpertChatMode] = list(get_args(AiExpertChatMode))

# Mode removed in August 2026 together with the OpenAI file upload and the hosted code interpreter.
# Persisted configurations may still carry it, so it is silently mapped to the fallback below.
REMOVED_AI_EXPERT_CHAT_MODE = "full_file"
REMOVED_AI_EXPERT_CHAT_MODE_FALLBACK: AiExpertChatMode = "relevant_chunks"


class AiExpertChatConfig(BaseModelDTO):
    """Configuration class for AI Expert functionality.

    This class defines all configurable parameters for the AI Expert chat system,
    including AI model settings, processing modes, and system prompts. It extends
    BaseModelDTO to provide serialization and validation capabilities.

    The AI Expert supports different processing modes:
        - full_text_chunk: The document's whole text, read from its stored snapshot, is integrated
          in the prompt. Exact text, but a document larger than the model's context window fails.
        - relevant_chunks: Only the passages of that document matching the user's question are
          retrieved, through the knowledge-base engine, and integrated in the prompt.

    The former 'full_file' mode (original file uploaded to OpenAI with code interpreter access)
    has been removed. A persisted configuration still carrying it loads as 'relevant_chunks'
    with a warning instead of raising a validation error.

    Attributes:
        prompt_file_placeholder (str): Placeholder token used in system prompt to represent
            the document name/identifier. Default: "[FILE]"

        system_prompt (str): The system prompt template that instructs the AI how to
            behave when analyzing documents. Should include the prompt_file_placeholder.

        mode (AiExpertChatMode): Processing mode for document analysis.
            Options: 'full_text_chunk', 'relevant_chunks'

        max_chunks (int): Maximum number of passages retrieved per question, in 'relevant_chunks'
            mode only — 'full_text_chunk' reads the whole snapshot and retrieves nothing.
            Range: 1-100, Default: 5

        model (str): Model to use for chat responses, as a pydantic-ai 'provider:model' string.
            Default: 'openai:gpt-4o'. A bare model name still loads, read as an OpenAI model.

        temperature (float): AI model temperature controlling response randomness.
            Range: 0.0 (focused) to 2.0 (creative), Default: 0.7

        placeholder_text (str): Placeholder text shown in the chat input field.
            Default: "Ask about this document..."

    Example:
        config = AiExpertConfig(
            mode='relevant_chunks',
            max_chunks=10,
            model='openai:gpt-4o-mini',
            temperature=0.5,
            placeholder_text="Ask me anything about the document..."
        )
    """

    # The removed mode was the previous default, so it is read on every config load. The fallback
    # warning is emitted once per process to keep it out of every page load and every chat message.
    removed_mode_warning_logged: ClassVar[bool] = False

    prompt_file_placeholder: str = "[FILE]"

    system_prompt: str = """You are an AI expert assistant specialized in analyzing and answering questions about the document "[FILE]".

You have access to the full content of this document and can provide detailed, accurate answers based on the information contained within it.

When answering questions:
- Use only the document content to support your answers
- Be specific and cite relevant sections when possible
- If something is not covered in the document, clearly state this
- Provide thorough, helpful explanations

The user is asking questions specifically about this document, so focus your responses on the document's content and context."""

    # Mode for the call to AI
    # 'full_text_chunk' the document's whole text, read from its snapshot, is integrated in the prompt
    # 'relevant_chunks' retrieves only the passages of that document matching the user's question
    mode: AiExpertChatMode = "relevant_chunks"

    # Number of passages to retrieve per question, 'relevant_chunks' mode only (1-100)
    max_chunks: int = 5

    # Model to use for chat, as a pydantic-ai "provider:model" string (e.g. "openai:gpt-4o").
    model: str = "openai:gpt-4o"

    # Temperature for the AI model (0.0 to 2.0)
    temperature: float = 0.7

    # Placeholder text for the chat input field
    placeholder_text: str = "Ask about this document..."

    @field_validator("mode", mode="before")
    @classmethod
    def map_removed_mode(cls, value: Any) -> Any:
        """Map the removed 'full_file' mode to the fallback mode instead of failing to load.

        Configurations persisted before the removal of the 'full_file' mode must keep loading,
        so the obsolete value is replaced by the fallback and a warning is logged once per
        process. Any other unknown value is left untouched and rejected by the regular Literal
        validation.

        Args:
            value (Any): Raw mode value coming from the persisted configuration.

        Returns:
            Any: The fallback mode when the removed mode is detected, the value unchanged otherwise.
        """
        if value == REMOVED_AI_EXPERT_CHAT_MODE:
            if not cls.removed_mode_warning_logged:
                cls.removed_mode_warning_logged = True
                Logger.warning(
                    f"AI Expert mode '{REMOVED_AI_EXPERT_CHAT_MODE}' has been removed, "
                    f"falling back to '{REMOVED_AI_EXPERT_CHAT_MODE_FALLBACK}'. "
                    "Update the AI Expert configuration to remove this warning."
                )
            return REMOVED_AI_EXPERT_CHAT_MODE_FALLBACK
        return value
