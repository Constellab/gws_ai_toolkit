import reflex as rx
from gws_ai_toolkit.rag.rag_app._rag_app.rag_app.components.config.sync_resource.sync_resource_state import (
    ResourceDTO, SyncResourceState)


def _resource_box(resource: ResourceDTO, hovered: bool):
    return rx.box(
        rx.text(resource.name),
        width="100%",
        padding="8px 16px",
        style={"background-color": "var(--gray-5)"} if hovered else {},
        # style=style,
        cursor="pointer",
        on_click=lambda: SyncResourceState.select_resource(resource.id)
    )


def _show_resource(resource: ResourceDTO, index: int):
    return rx.cond(index == SyncResourceState.hover_index,
                   _resource_box(resource, True),
                   _resource_box(resource, False)
                   )


def search_resource():
    return rx.vstack(
        rx.text("Search and select a resource to view its sync status and send it to the RAG platform.",
                style={"color": "var(--blue-11)", "background": "var(--blue-3)", "padding": "12px", "border_radius": "6px"}),

        rx.popover.root(
            rx.popover.trigger(
                rx.box(
                    rx.input(
                        placeholder="Search here...", value=SyncResourceState.text,
                        on_change=SyncResourceState.set_text,
                        on_key_down=SyncResourceState.on_input_key_down,
                        on_focus=SyncResourceState.on_input_focus,
                    ))
            ),
            rx.popover.content(
                rx.flex(
                    rx.cond(
                        SyncResourceState.no_resources_found, rx.text("No resources found", padding='1em'),
                        rx.scroll_area(
                            rx.vstack(
                                rx.foreach(
                                    SyncResourceState.resources_infos, lambda resource,
                                    index: _show_resource(resource, index)),
                                spacing="0"
                            ),
                            max_height="256px",)),
                    direction="column"),
                padding='0',),
            display='none',
            open=SyncResourceState.popover_opened),

        _resource_info_section(),

        spacing="4"
    )


def _resource_info_section():
    return rx.cond(
        SyncResourceState.selected_resource_info, rx.vstack(
            rx.text(f"Selected resource: {SyncResourceState.selected_resource_info.name}", weight="bold"),
            rx.cond(
                ~SyncResourceState.is_selected_resource_compatible, rx.text(
                    "The resource is not compatible with the RAG platform.",
                    style={"color": "var(--amber-11)", "background": "var(--amber-3)", "padding": "12px",
                           "border_radius": "6px"}),
                rx.cond(
                    SyncResourceState.is_selected_resource_synced, _synced_resource_info(),
                    _unsynced_resource_info())),
            spacing="3"))


def _synced_resource_info():
    return rx.vstack(
        rx.text("The resource is already sent to the RAG platform."),
        rx.text(f"RAG knowledge base id: {SyncResourceState.selected_resource_dataset_id}"),
        rx.text(f"RAG document id: {SyncResourceState.selected_resource_document_id}"),
        rx.text(f"RAG sync date: {SyncResourceState.selected_resource_sync_date}"),
        rx.hstack(
            rx.button(
                rx.spinner(loading=SyncResourceState.send_to_rag_is_loading),
                rx.text("Resend to RAG"),
                on_click=SyncResourceState.send_to_rag,
                variant="solid"
            ),
            rx.alert_dialog.root(
                rx.alert_dialog.trigger(
                    rx.button(
                        rx.spinner(loading=SyncResourceState.delete_from_rag_is_loading),
                        "Delete from RAG", color_scheme="red")),
                rx.alert_dialog.content(
                    rx.alert_dialog.title("Delete from RAG"),
                    rx.alert_dialog.description(
                        "Are you sure? This resource will be deleted from the RAG platform.",),
                    rx.flex(
                        rx.alert_dialog.cancel(rx.button("Cancel"),),
                        rx.alert_dialog.action(
                            rx.button(
                                "Delete from RAG", on_click=SyncResourceState.delete_from_rag, color_scheme="red"),),
                        spacing="3",),),),
            spacing="2"),
        spacing="2")


def _unsynced_resource_info():
    return rx.vstack(
        rx.text("The resource is not sent to the RAG platform."),
        rx.button(
            rx.spinner(loading=SyncResourceState.send_to_rag_is_loading),
            rx.text("Send to RAG"),
            on_click=SyncResourceState.send_to_rag,
            variant="solid"
        ),
        spacing="2"
    )
