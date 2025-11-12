

from typing import Callable

import reflex as rx
from gws_reflex_main import dialog_header, loader_section

from gws_ai_toolkit._app.ai_rag import ChatStateBase

from .associated_resources_state import AssociatedResourcesState, ResourceDTO


def _resource_item(resource: ResourceDTO) -> rx.Component:
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
    return rx.hstack(
        rx.icon("file-text", size=16),
        rx.text(resource.name, size="1"),
        rx.spacer(),
        rx.menu.root(
            rx.menu.trigger(
                rx.button(
                    rx.icon("ellipsis-vertical", size=16),
                    variant="ghost", cursor='pointer')),
            rx.menu.content(
                rx.cond(
                    resource.is_in_rag,
                    rx.menu.item(
                        rx.icon("bot", size=16),
                        "Open AI Expert",
                        on_click=lambda: AssociatedResourcesState.open_ai_expert_from_resource(
                            resource.id),
                        cursor='pointer'),
                ),
                rx.cond(
                    resource.is_excel, rx.menu.item(
                        rx.icon("table", size=16),
                        "Open Excel AI Table",
                        on_click=lambda: AssociatedResourcesState.open_ai_table_from_resource(
                            resource.id),
                        cursor='pointer'),
                ),
                rx.menu.item(
                    rx.icon("external-link", size=16),
                    "Open document",
                    on_click=lambda: AssociatedResourcesState.open_document_from_resource(
                        resource.id),
                    cursor='pointer')
            ),
            flex_shrink="0"),
        align_items="center",)


def associated_resources_section(_: ChatStateBase) -> rx.Component:
    """Left sidebar component with associated documents list."""
    return rx.box(
        rx.vstack(
            rx.heading("Associated documents", size="4", margin_bottom="3"),
            loader_section(
                content=rx.vstack(
                    rx.foreach(AssociatedResourcesState.linked_resources_data, _resource_item),
                    spacing="2", align="stretch",),
                is_loading=AssociatedResourcesState.is_loading,),
            spacing="3", width="100%"),
        on_mount=AssociatedResourcesState.load_from_expert_state
    )


def associated_resources_dialog() -> rx.Component:
    """Dialog component displaying the associated documents list.

    Args:
        _: ChatStateBase (unused, for consistency with other components)

    Returns:
        rx.Component: Dialog with associated documents list
    """
    return rx.dialog.root(
        rx.dialog.content(
            dialog_header("Associated documents", close=AssociatedResourcesState.close_dialog),
            rx.box(
                loader_section(
                    content=rx.vstack(
                        rx.foreach(AssociatedResourcesState.linked_resources_data, _resource_item),
                        spacing="2",
                        align="stretch",
                    ),
                    is_loading=AssociatedResourcesState.is_loading,
                ),
                margin_bottom="4",
            ),
        ),
        open=AssociatedResourcesState.is_dialog_open,
    )
