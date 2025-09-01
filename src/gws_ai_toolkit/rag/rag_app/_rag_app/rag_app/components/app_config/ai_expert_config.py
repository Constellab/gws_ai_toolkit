

from dataclasses import dataclass
from typing import Callable, List, Literal

import reflex as rx
from gws_core import BaseModelDTO


@dataclass
class AiExpertConfigUI:

    # Add custom button on top right of the header
    header_buttons: Callable[[], List[rx.Component]] | None = None


class AiExpertConfig(BaseModelDTO):

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
    # 'text_chunk' basic chat call where the document content (as text) is integrated in the prompt
    # 'full_file' mode where the file is uploaded and the AI has access to the original file to answer
    mode: Literal['text_chunk', 'full_file'] = 'full_file'
