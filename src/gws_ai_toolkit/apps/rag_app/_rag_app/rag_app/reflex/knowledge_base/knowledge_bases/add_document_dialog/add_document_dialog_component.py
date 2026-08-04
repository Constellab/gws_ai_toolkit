"""The add-document dialog.

Two shapes in one dialog, chosen by the selected source type: a drop zone for the built-in ``upload``
provider (whose bytes are the snapshot) and an id field for any other registered source (which is
fetched from its own system). The select itself is a ``rx.foreach`` over the registry, so a provider
another brick registers appears here with no change to this file.

The rejection list stays on screen after a failed attempt. A toast fades, and a faded toast is
indistinguishable from a file that was quietly skipped.
"""

import reflex as rx

from ...core.form_field_component import form_field
from .add_document_dialog_state import (
    MAX_UPLOAD_FILES,
    UPLOAD_ZONE_ID,
    AddDocumentDialogState,
)


def add_document_button() -> rx.Component:
    """The button that opens the add-document dialog, with the dialog itself attached."""
    return rx.fragment(
        rx.button(
            rx.icon("plus", size=16),
            "Add documents",
            on_click=AddDocumentDialogState.open_dialog,
        ),
        add_document_dialog(),
    )


def add_document_dialog() -> rx.Component:
    """The dialog: a source-type select, then the form that source needs."""
    return rx.dialog.root(
        rx.dialog.content(
            rx.dialog.title("Add documents"),
            rx.dialog.description(
                "Documents are added first and indexed straight after. A file that cannot be "
                "indexed is refused here, with the reason.",
                size="2",
                color="var(--gray-11)",
                margin_bottom="1rem",
            ),
            rx.vstack(
                _source_type_select(),
                rx.cond(
                    AddDocumentDialogState.is_upload_source,
                    _upload_zone(),
                    _source_document_form(),
                ),
                _rejections_panel(),
                rx.hstack(
                    rx.spacer(),
                    rx.button(
                        "Close",
                        variant="soft",
                        on_click=AddDocumentDialogState.close_dialog,
                    ),
                    width="100%",
                ),
                spacing="4",
                width="100%",
            ),
            on_interact_outside=AddDocumentDialogState.close_dialog,
            on_escape_key_down=AddDocumentDialogState.close_dialog,
            max_width="34rem",
        ),
        open=AddDocumentDialogState.dialog_open,
    )


def _source_type_select() -> rx.Component:
    """The source-type select, built from the registered providers."""
    return rx.vstack(
        rx.text("Source", size="2", weight="medium"),
        rx.select.root(
            rx.select.trigger(placeholder="Choose a source"),
            rx.select.content(
                rx.foreach(
                    AddDocumentDialogState.source_types,
                    lambda source_type: rx.select.item(source_type, value=source_type),
                ),
            ),
            value=AddDocumentDialogState.selected_source_type,
            on_change=AddDocumentDialogState.set_selected_source_type,
        ),
        spacing="1",
        width="100%",
    )


def _upload_zone() -> rx.Component:
    """The drop zone for the built-in upload provider."""
    return rx.cond(
        AddDocumentDialogState.is_uploading,
        rx.vstack(
            rx.spinner(size="3"),
            rx.text("Uploading...", size="2", color="var(--gray-11)"),
            align="center",
            justify="center",
            spacing="3",
            width="100%",
            min_height="9rem",
        ),
        rx.upload.root(
            rx.vstack(
                rx.icon("upload", size=28, color="var(--accent-10)"),
                rx.text(
                    "Click to upload or drag and drop",
                    size="2",
                    weight="medium",
                    color="var(--accent-10)",
                ),
                rx.text(
                    AddDocumentDialogState.accepted_formats_label,
                    size="1",
                    color="var(--gray-10)",
                ),
                align="center",
                justify="center",
                spacing="2",
                height="100%",
                padding="1.5rem",
            ),
            id=UPLOAD_ZONE_ID,
            multiple=True,
            max_files=MAX_UPLOAD_FILES,
            on_drop=AddDocumentDialogState.handle_upload(
                rx.upload_files(
                    upload_id=UPLOAD_ZONE_ID,
                    on_upload_progress=AddDocumentDialogState.handle_upload_progress,
                )
            ),
            border="2px dashed var(--accent-8)",
            border_radius="0.5rem",
            background="var(--accent-2)",
            cursor="pointer",
            width="100%",
            min_height="9rem",
        ),
    )


def _source_document_form() -> rx.Component:
    """The form a non-upload source needs: the document's id in that system, plus extras."""
    return rx.vstack(
        form_field(
            "Document id in the source",
            rx.input(
                placeholder="Id of the document in the source system",
                value=AddDocumentDialogState.source_id,
                on_change=AddDocumentDialogState.set_source_id,
                width="100%",
            ),
        ),
        form_field(
            "Source metadata (optional JSON)",
            rx.text_area(
                placeholder='{"key": "value"}',
                value=AddDocumentDialogState.source_metadata_json,
                on_change=AddDocumentDialogState.set_source_metadata_json,
                width="100%",
                rows="3",
            ),
        ),
        rx.button(
            rx.spinner(loading=AddDocumentDialogState.is_adding),
            "Add document",
            on_click=AddDocumentDialogState.add_from_source,
            disabled=AddDocumentDialogState.is_adding,
        ),
        spacing="3",
        width="100%",
    )


def _rejections_panel() -> rx.Component:
    """The reasons the last attempt refused documents, one line each."""
    return rx.cond(
        AddDocumentDialogState.has_rejections,
        rx.vstack(
            rx.hstack(
                rx.icon("circle-alert", size=16, color="var(--amber-11)"),
                rx.text("Not added", size="2", weight="medium", color="var(--amber-11)"),
                align="center",
                spacing="2",
            ),
            rx.foreach(
                AddDocumentDialogState.rejections,
                lambda rejection: rx.text(rejection, size="1", color="var(--amber-11)"),
            ),
            background="var(--amber-3)",
            border_radius="0.375rem",
            padding="0.75rem",
            spacing="1",
            width="100%",
        ),
    )
