"""Opening a knowledge-base document from the app — the one place that decides how.

A document's own provider decides: a lab resource can be opened through a share link, an uploaded file
cannot be opened anywhere but here. ``KnowledgeBaseService.get_document_open_action`` is what answers
that question (falling back to the snapshot for a provider that is not registered at all), and this
module is what turns its answer into a Reflex event.

The snapshot is served over HTTP through :class:`ReflexDownloadService` rather than pushed through the
websocket as ``rx.download(data=...)``: documents run up to 15 MB, and a payload that size shipped
through the event channel freezes the UI while it travels. **The app must mount the download route**
(``app.api_transformer = ReflexDownloadService.build_api()``) for this to work.
"""

import mimetypes

import reflex as rx
from gws_ai_toolkit.models.knowledge_base.knowledge_base_document import KnowledgeBaseDocument
from gws_ai_toolkit.models.knowledge_base.knowledge_base_service import KnowledgeBaseService
from gws_ai_toolkit.rag.knowledge_base.sources.knowledge_base_source import SourceOpenActionType
from gws_reflex_main import ReflexDownloadService

# What a file of unrecognised type is served as. The browser then downloads it rather than guessing,
# which is the safe outcome for a document the app only stores.
DEFAULT_MEDIA_TYPE = "application/octet-stream"

# A document deleted from its knowledge base while a page still names it — a chat kept open, a
# conversation reopened from history. Nothing is broken, so it is said once, the same way everywhere.
DOCUMENT_GONE_MESSAGE = "This document is no longer in its knowledge base, so it cannot be opened."


def build_open_document_event_for_id(document_id: str) -> rx.event.EventSpec | None:
    """The event opening the document with this id, or the one explaining why it cannot be opened.

    The id-taking form, for the callers that hold a document id rather than a row: a chat header, a
    source pill, an admin history page. Reads the database, so it must be called inside an
    authenticated context.

    :param document_id: the knowledge-base document to open
    :return: the event to yield or return, a toast if the document is gone, or ``None`` if its source
             offers no way to open it
    """
    document = KnowledgeBaseService().get_document(document_id)
    if document is None:
        return rx.toast.error(DOCUMENT_GONE_MESSAGE)

    return build_open_document_event(document)


def build_open_document_event(document: KnowledgeBaseDocument) -> rx.event.EventSpec | None:
    """The event opening this document, as its own source decides.

    :param document: the document row to open; its ``snapshot_path`` is read, so this may only be
                     called from the backend
    :return: the event to yield or return, or ``None`` if the source offers no way to open it
    """
    open_action = KnowledgeBaseService().get_document_open_action(document)
    if open_action is None:
        return None

    if open_action.type == SourceOpenActionType.EXTERNAL_LINK and open_action.url:
        return rx.redirect(open_action.url, is_external=True)

    media_type = mimetypes.guess_type(document.filename)[0] or DEFAULT_MEDIA_TYPE
    token = ReflexDownloadService.register(
        document.snapshot_path, filename=document.filename, media_type=media_type
    )
    return ReflexDownloadService.trigger_download(token, document.filename)
