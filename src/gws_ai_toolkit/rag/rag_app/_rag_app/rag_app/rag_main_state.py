

import reflex as rx
from gws_reflex_main import ReflexMainState


class RagAppState(ReflexMainState, rx.State):
    """Main state define to access methods from ReflexMainState."""

    bonjour: str = 's'
