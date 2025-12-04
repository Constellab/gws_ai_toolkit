import reflex as rx

from ..document_chunks.document_chunks_component import document_chunks_dialog, load_chunks_button
from .sync_resource_state import ResourceDTO, SyncResourceState


def _resource_box(resource: ResourceDTO, hovered: bool):
    return rx.box(
        rx.text(resource.name),
        width="100%",
        padding="8px 16px",
        style={"background-color": "var(--gray-5)"} if hovered else {},
        # style=style,
        on_click=lambda: SyncResourceState.select_resource(resource.id),
    )


def _show_resource(resource: ResourceDTO, index: int):
    return rx.cond(
        index == SyncResourceState.hover_index,
        _resource_box(resource, True),
        _resource_box(resource, False),
    )


def search_resource():
    return rx.vstack(
        rx.text(
            "Search and select a resource to view its sync status and send it to the RAG platform.",
            style={
                "color": "var(--blue-11)",
                "background": "var(--blue-3)",
                "padding": "12px",
                "border_radius": "6px",
            },
        ),
        rx.popover.root(
            rx.popover.trigger(
                rx.box(
                    rx.input(
                        placeholder="Search here...",
                        value=SyncResourceState.text,
                        on_change=SyncResourceState.set_text,
                        on_key_down=SyncResourceState.on_input_key_down,
                        on_focus=SyncResourceState.on_input_focus,
                    )
                )
            ),
            rx.popover.content(
                rx.flex(
                    rx.cond(
                        SyncResourceState.no_resources_found,
                        rx.text("No resources found", padding="1em"),
                        rx.scroll_area(
                            rx.vstack(
                                rx.foreach(SyncResourceState.resources_infos, _show_resource),
                                spacing="0",
                            ),
                            max_height="256px",
                        ),
                    ),
                    direction="column",
                ),
                padding="0",
            ),
            display="none",
            open=SyncResourceState.popover_opened,
        ),
        _resource_info_section(),
        # Chunks dialog (available for all resources)
        document_chunks_dialog(),
        spacing="4",
    )


def _resource_info_section():
    return rx.cond(
        SyncResourceState.selected_resource_info,
        rx.vstack(
            rx.hstack(
                rx.text(
                    f"Selected resource: {SyncResourceState.selected_resource_info.name}",
                    weight="bold",
                ),
                rx.button(
                    "Refresh",
                    on_click=SyncResourceState.refresh_selected_resource,
                    cursor="pointer",
                ),
                align_items="center",
            ),
            rx.cond(
                ~SyncResourceState.is_selected_resource_compatible,
                rx.text(
                    "The resource is not compatible with the RAG platform.",
                    style={
                        "color": "var(--amber-11)",
                        "background": "var(--amber-3)",
                        "padding": "12px",
                        "border_radius": "6px",
                    },
                ),
                rx.cond(
                    SyncResourceState.is_selected_resource_synced,
                    _synced_resource_info(),
                    _unsynced_resource_info(),
                ),
            ),
            spacing="3",
        ),
    )


def _synced_resource_info():
    return rx.vstack(
        rx.text("The resource is already sent to the RAG platform."),
        rx.text(f"RAG knowledge base id: {SyncResourceState.selected_resource_dataset_id}"),
        rx.text(f"RAG document id: {SyncResourceState.selected_resource_document_id}"),
        rx.text(f"RAG sync date: {SyncResourceState.selected_resource_sync_date}"),
        rx.cond(
            SyncResourceState.selected_resource_document,
            rx.vstack(
                rx.text(
                    f"Document name: {SyncResourceState.selected_resource_document.name}",
                    weight="medium",
                ),
                rx.text(
                    f"Parse status: {SyncResourceState.selected_resource_document.parsed_status}",
                    style={
                        "color": rx.match(
                            SyncResourceState.selected_resource_document.parsed_status,
                            ("DONE", "var(--green-11)"),
                            ("ERROR", "var(--red-11)"),
                            ("RUNNING", "var(--blue-11)"),
                            "var(--amber-11)",
                        )
                    },
                ),
                spacing="1",
            ),
        ),
        rx.hstack(
            rx.button(
                rx.spinner(loading=SyncResourceState.send_to_rag_is_loading),
                rx.text("Resend to RAG"),
                disabled=SyncResourceState.send_to_rag_is_loading,
                on_click=SyncResourceState.send_to_rag,
                variant="solid",
                cursor="pointer",
            ),
            rx.button(
                rx.spinner(loading=SyncResourceState.parse_document_is_loading),
                rx.text("Parse document"),
                disabled=SyncResourceState.parse_document_is_loading,
                on_click=SyncResourceState.parse_document,
                variant="outline",
                cursor="pointer",
            ),
            load_chunks_button(
                SyncResourceState.selected_resource_dataset_id,
                SyncResourceState.selected_resource_document_id,
            ),
            rx.alert_dialog.root(
                rx.alert_dialog.trigger(
                    rx.button(
                        rx.spinner(loading=SyncResourceState.delete_from_rag_is_loading),
                        "Delete from RAG",
                        disabled=SyncResourceState.delete_from_rag_is_loading,
                        color_scheme="red",
                        cursor="pointer",
                    )
                ),
                rx.alert_dialog.content(
                    rx.alert_dialog.title("Delete from RAG"),
                    rx.alert_dialog.description(
                        "Are you sure? This resource will be deleted from the RAG platform.",
                    ),
                    rx.flex(
                        rx.alert_dialog.cancel(rx.button("Cancel", cursor="pointer")),
                        rx.alert_dialog.action(
                            rx.button(
                                "Delete from RAG",
                                on_click=SyncResourceState.delete_from_rag,
                                color_scheme="red",
                                cursor="pointer",
                            ),
                        ),
                        spacing="3",
                    ),
                ),
            ),
            spacing="2",
        ),
        spacing="2",
    )


def _unsynced_resource_info():
    return rx.vstack(
        rx.text("The resource is not sent to the RAG platform."),
        rx.button(
            rx.spinner(loading=SyncResourceState.send_to_rag_is_loading),
            rx.text("Send to RAG"),
            disabled=SyncResourceState.send_to_rag_is_loading,
            on_click=SyncResourceState.send_to_rag,
            variant="solid",
            cursor="pointer",
        ),
        spacing="2",
    )
