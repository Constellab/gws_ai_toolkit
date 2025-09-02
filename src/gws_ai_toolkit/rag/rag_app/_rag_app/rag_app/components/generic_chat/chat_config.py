from dataclasses import dataclass
from typing import Callable, List

import reflex as rx

from gws_ai_toolkit.rag.common.rag_models import RagChunk

from .chat_state_base import ChatStateBase


@dataclass
class ChatConfig:
    """Simple configuration for chat component - only state is configurable"""

    # State configuration - this is the only customizable part
    state: ChatStateBase

    # Add custom button on top right of the header
    header_buttons: Callable[[ChatStateBase], List[rx.Component]] | None = None

    sources_component: Callable[[List[RagChunk], ChatStateBase], rx.Component] | None = None
