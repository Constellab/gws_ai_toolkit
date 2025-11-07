
from typing import Type

import reflex as rx

from gws_ai_toolkit._app.ai_rag import ChatStateBase

from .custom_ai_expert_state import AssociatedResourceState, ResourceDTO


def _resource_item(resource: ResourceDTO, state: AssociatedResourceState) -> rx.Component:
    """Individual resource item with document info and action menu.

    Renders a single resource with document name and dropdown menu
    for actions like opening in AI Expert or viewing the original document.

    Args:
        resource_name (str): Name of the resource
        resource_id (str): ID of the resource
        state (CustomAiExpertState): State for handling actions

    Returns:
        rx.Component: Formatted resource item with name and actions menu
    """
    return rx.box(
        rx.hstack(
            rx.icon("file-text", size=16),
            rx.text(resource.name, size="1"),
            rx.spacer(),
            rx.menu.root(
                rx.menu.trigger(
                    rx.button(
                        rx.icon("ellipsis-vertical", size=16),
                        variant="ghost",
                        cursor='pointer'
                    )
                ),
                rx.menu.content(
                    rx.cond(
                        resource.is_in_rag,
                        rx.fragment(
                            rx.menu.item(
                                rx.icon("bot", size=16),
                                "Open AI Expert",
                                on_click=lambda: state.open_ai_expert_from_resource(resource.id),
                                cursor='pointer'
                            ),
                            rx.menu.item(
                                rx.icon("external-link", size=16),
                                "Open document",
                                on_click=lambda: state.open_document_from_resource(resource.id),
                                cursor='pointer'
                            ),
                        )
                    ),
                    rx.cond(
                        resource.is_excel,
                        rx.menu.item(
                            rx.icon("table", size=16),
                            "Open Excel AI Table",
                            on_click=lambda: state.open_ai_table_from_resource(resource.id),
                            cursor='pointer'
                        ),
                    )
                ),
                flex_shrink="0"
            ),
            align_items="center",
        ),
        padding="2",
    )


def custom_left_sidebar(_: ChatStateBase, state: Type[AssociatedResourceState]) -> rx.Component:
    """Left sidebar component with associated documents list."""
    return rx.box(
        rx.cond(
            state.linked_resources_data,
            rx.vstack(
                rx.heading("Associated documents", size="4", margin_bottom="3"),
                rx.vstack(
                    rx.foreach(state.linked_resources_data, lambda resource_data: _resource_item(resource_data, state)),
                    spacing="2",
                    align="stretch",
                ),
                spacing="3",
                width="100%",
            ),
        ),
        padding="4",
        on_mount=state.load_linked_resources,
    )
