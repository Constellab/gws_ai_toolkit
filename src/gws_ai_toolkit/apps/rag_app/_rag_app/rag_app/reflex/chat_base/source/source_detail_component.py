import reflex as rx
from gws_reflex_base.component.reflex_dialog_components import dialog_header

from ..conversation_chat_state_base import ConversationChatStateBase
from .source_detail_state import SourceDetailState
from .source_menu_component import CustomSourceMenuButtons, source_menu_button


def source_detail_dialog(
    state: ConversationChatStateBase,
    custom_menu_items: CustomSourceMenuButtons | None = None,
) -> rx.Component:
    """Create a dialog component to display source details.

    This dialog displays the details of a ChatMessageSource, including:
    - Document name as the dialog title
    - Chunk content as markdown in the dialog body

    The dialog opens when the user clicks on a source button in the chat
    and loads the source data from the database.

    Returns:
        rx.Component: A dialog component with source details
    """
    return rx.dialog.root(
        rx.dialog.content(
            rx.cond(
                SourceDetailState.is_loading,
                # Loading state
                rx.vstack(
                    dialog_header("Loading source...", close=SourceDetailState.close_dialog),
                    rx.center(
                        rx.spinner(size="3"),
                        padding="4",
                    ),
                ),
                # Loaded state
                rx.cond(
                    SourceDetailState.source,
                    # Source loaded successfully
                    rx.vstack(
                        dialog_header(
                            "Source: " + SourceDetailState.source.document_name,
                            close=SourceDetailState.close_dialog,
                            additional_actions=source_menu_button(
                                SourceDetailState.source_front,
                                state,
                                custom_menu_items,
                            ),
                        ),
                        rx.box(
                            rx.cond(
                                SourceDetailState.source.chunk,
                                rx.cond(
                                    SourceDetailState.source.chunk.content,
                                    rx.markdown(SourceDetailState.source.chunk.content),
                                    rx.text(
                                        "No content available for this source.",
                                        color="gray",
                                        font_style="italic",
                                    ),
                                ),
                                rx.text(
                                    "No chunk data available for this source.",
                                    color="gray",
                                    font_style="italic",
                                ),
                            ),
                            padding="4",
                            max_height="60vh",
                            overflow_y="auto",
                        ),
                        spacing="2",
                        width="100%",
                    ),
                ),
            ),
            max_width="800px",
            width="90vw",
        ),
        open=SourceDetailState.is_dialog_open,
    )
