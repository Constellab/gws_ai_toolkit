import reflex as rx

from ...states.config_state import ConfigState


def resource_info_card(resource) -> rx.Component:
    """Display information about the selected resource."""
    return rx.cond(
        resource,
        rx.box(
            rx.vstack(
                rx.heading("Resource Information", size="4"),
                rx.hstack(
                    rx.text("Name:", font_weight="medium"),
                    rx.text("Sample Resource"),  # resource.resource_model.name in real implementation
                    spacing="2",
                ),
                rx.hstack(
                    rx.text("ID:", font_weight="medium"),
                    rx.text("sample-id", font_family="mono", font_size="sm"),  # resource.resource_model.id
                    spacing="2",
                ),
                rx.cond(
                    True,  # resource.is_synced_with_rag() in real implementation
                    rx.vstack(
                        rx.hstack(
                            rx.text("RAG Dataset ID:", font_weight="medium"),
                            rx.text("sample-dataset-id", font_family="mono", font_size="sm"),
                            spacing="2",
                        ),
                        rx.hstack(
                            rx.text("RAG Document ID:", font_weight="medium"),
                            rx.text("sample-doc-id", font_family="mono", font_size="sm"),
                            spacing="2",
                        ),
                        rx.hstack(
                            rx.text("Sync Date:", font_weight="medium"),
                            rx.text("2024-01-01 12:00:00", font_size="sm"),
                            spacing="2",
                        ),
                        spacing="2",
                        align="start",
                    )
                ),
                spacing="3",
                align="start",
            ),
            p="4",
            border="1px solid",
            border_color="gray.200",
            border_radius="md",
            bg="gray.50",
        )
    )


def resource_search() -> rx.Component:
    """Resource search and selection interface."""
    return rx.vstack(
        rx.heading("Resource Selection", size="4"),
        rx.input(
            placeholder="Search for resources...",
            # on_change=ConfigState.search_resources,
            width="100%",
        ),

        # This would be replaced with actual resource selection logic
        # rx.button(
        #     "Select Sample Resource",
        #     on_click=lambda : ConfigState.set_selected_resource("sample-id"),
        #     size="2",
        #     variant="outline",
        # ),
        spacing="3",
        align="start",
        width="100%",
    )


def resource_selector() -> rx.Component:
    """Main resource selector component."""
    return rx.vstack(
        resource_search(),
        resource_info_card(ConfigState.selected_resource_id),
        spacing="4",
        align="start",
        width="100%",
    )
