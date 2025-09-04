

from dataclasses import dataclass
from typing import Callable, List, Literal

import reflex as rx
from gws_core import BaseModelDTO

AiExpertChatMode = Literal['full_text_chunk', 'relevant_chunks', 'full_file']


@dataclass
class AiExpertConfigUI:
    """UI configuration class for AI Expert interface customization.
    
    This dataclass defines UI-specific configuration options for the AI Expert
    component, allowing customization of the interface elements and behavior.
    
    Attributes:
        header_buttons (Callable[[], List[rx.Component]] | None): Optional callable
            that returns a list of custom header buttons to display in the AI Expert
            chat interface. If None, default header buttons are used.
            
    Example:
        def custom_buttons() -> List[rx.Component]:
            return [rx.button("Custom Action", on_click=custom_handler)]
            
        config = AiExpertConfigUI(header_buttons=custom_buttons)
    """

    # Add custom button on top right of the header
    header_buttons: Callable[[], List[rx.Component]] | None = None


class AiExpertConfig(BaseModelDTO):
    """Configuration class for AI Expert functionality.
    
    This class defines all configurable parameters for the AI Expert chat system,
    including AI model settings, processing modes, and system prompts. It extends
    BaseModelDTO to provide serialization and validation capabilities.
    
    The AI Expert supports different processing modes:
        - full_text_chunk: Document content (all chunks) converted to text and integrated in prompt
        - relevant_chunks: Only most relevant chunks retrieved based on user question
        - full_file: Original file uploaded to AI with access to complete document structure
        
    Attributes:
        prompt_file_placeholder (str): Placeholder token used in system prompt to represent
            the document name/identifier. Default: "[FILE]"
            
        system_prompt (str): The system prompt template that instructs the AI how to
            behave when analyzing documents. Should include the prompt_file_placeholder.
            
        mode (AiExpertChatMode): Processing mode for document analysis.
            Options: 'full_text_chunk', 'relevant_chunks', 'full_file'
            
        max_chunks (int): Maximum number of chunks to retrieve in 'relevant_chunks' mode.
            Range: 1-100, Default: 5
            
        model (str): OpenAI model identifier to use for chat responses.
            Default: 'gpt-4o'
            
        temperature (float): AI model temperature controlling response randomness.
            Range: 0.0 (focused) to 2.0 (creative), Default: 0.7
            
    Example:
        config = AiExpertConfig(
            mode='relevant_chunks',
            max_chunks=10,
            model='gpt-4o-mini',
            temperature=0.5
        )
    """

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
    # 'full_text_chunk' basic chat call where the document content (all chunks as text) is integrated in the prompt
    # 'relevant_chunks' retrieves only the most relevant chunks based on the user's question
    # 'full_file' mode where the file is uploaded and the AI has access to the original file to answer
    mode: AiExpertChatMode = 'full_file'

    # Number of chunks to retrieve for relevant_chunks mode (1-100)
    max_chunks: int = 5

    # OpenAI model to use for chat
    model: str = 'gpt-4o'

    # Temperature for the AI model (0.0 to 2.0)
    temperature: float = 0.7
