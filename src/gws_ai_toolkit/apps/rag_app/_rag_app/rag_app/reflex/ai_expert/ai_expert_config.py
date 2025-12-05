from collections.abc import Callable
from dataclasses import dataclass
from typing import Literal

import reflex as rx

AiExpertChatMode = Literal["full_text_chunk", "relevant_chunks", "full_file"]


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
    header_buttons: Callable[[], list[rx.Component]] | None = None
