"""State of the add-document dialog: one dialog, every registered source, no silent skips.

**The source-type select is built from the registry**, never from a list written here. Other bricks
register their own providers at load time and this app must not know their names — the same inversion
``@credentials_type`` uses. A hard-coded list would be wrong the day a brick is installed.

**A rejected file is reported with its reason.** ``UnsupportedDocumentFormatError`` and
``DocumentTooLargeError`` each carry a message naming what was wrong (which formats are indexable, how
big the file was against the cap), and a provider that cannot produce the document says so too. Those
messages are collected into :attr:`AddDocumentDialogState.rejections` and shown *inside the dialog*,
not only as a toast: a toast that has faded is indistinguishable from a silent skip, and "nothing
happened" reads as success.

This is the one place in this feature where a broad ``except`` is right. A user can drop ten files at
once, and one unsupported format must not abandon the other nine — so each file is admitted or
rejected on its own, and every rejection keeps its message.

**Import by tag is the second mode of the same dialog**, offered for the ``resource`` provider. It is
the one place in this app that names a provider besides ``upload``, and it has to: a criterion is
provider-specific, and "tag key / tag value" is a form only the lab-resource provider can be asked to
fill. The select above it is still built from the registry, so a brick's own provider still appears —
it simply gets the single-document form until someone writes its criterion form.

Its report is a **dialog, not a toast**. Reporting skips matters more here than on a single add: a tag
matching fifty resources of which eight are incompatible must not read as a clean success, and fifty
lines is not something a toast can carry.
"""

import json
from collections.abc import AsyncGenerator
from typing import Any

import reflex as rx
from gws_ai_toolkit.models.knowledge_base.knowledge_base_dto import (
    ImportedDocumentDTO,
    SkippedDocumentDTO,
)
from gws_ai_toolkit.models.knowledge_base.knowledge_base_service import KnowledgeBaseService
from gws_ai_toolkit.rag.knowledge_base.document_compatibility import MAX_DOCUMENT_SIZE_MB
from gws_ai_toolkit.rag.knowledge_base.document_loader import SUPPORTED_EXTENSIONS
from gws_ai_toolkit.rag.knowledge_base.sources.knowledge_base_source import (
    KnowledgeBaseDocumentSourceRegistry,
)
from gws_ai_toolkit.rag.knowledge_base.sources.resource_source import (
    RESOURCE_SOURCE_TYPE,
    TAG_KEY_CRITERION,
    TAG_VALUE_CRITERION,
)
from gws_ai_toolkit.rag.knowledge_base.sources.upload_source import UPLOAD_SOURCE_TYPE
from gws_core import Logger
from gws_reflex_main import ReflexAppException, ReflexMainState

from ...core.knowledge_base_app_state import KnowledgeBaseAppState
from ...core.knowledge_base_errors import DOCUMENT_REJECTION_ERRORS
from ..knowledge_base_detail_state import (
    INDEXING_IN_PROGRESS_MESSAGE,
    KnowledgeBaseDetailState,
)

# Id of the ``rx.upload`` zone. Reflex keys the selected-file list by it, so clearing the zone after an
# upload needs the same string.
UPLOAD_ZONE_ID = "knowledge_base_document_upload"

# What the drop zone advertises, derived from the loader's own set so the two cannot drift.
ACCEPTED_EXTENSIONS_LABEL = ", ".join(sorted(SUPPORTED_EXTENSIONS))

MAX_UPLOAD_FILES = 10

# The two shapes the dialog can take for a source that is not an upload.
ADD_MODE_SINGLE = "single"
ADD_MODE_TAG = "tag"


class AddDocumentDialogState(rx.State):
    """The add-document dialog: pick a source, then upload bytes, name a document, or import a tag."""

    dialog_open: bool = False

    # Source types, read from the registry when the dialog opens rather than at import time: a brick
    # loaded after this module would otherwise be missing from the select.
    source_types: list[str] = []
    selected_source_type: str = UPLOAD_SOURCE_TYPE

    # Non-upload sources: the id of the document in the source system, plus optional provider extras.
    source_id: str = ""
    source_metadata_json: str = ""

    # Which form a non-upload source shows: one document, or every resource carrying a tag.
    add_mode: str = ADD_MODE_SINGLE
    tag_key: str = ""
    tag_value: str = ""

    is_uploading: bool = False
    is_adding: bool = False
    is_importing: bool = False

    # One line per file that was refused, each carrying the reason. Cleared when the dialog opens, so
    # what is on screen always belongs to the attempt the user just made.
    rejections: list[str] = []

    # The last import's outcome, held as two plain lists rather than one optional report var: a
    # ``rx.foreach`` over a nested attribute of a possibly-None var is fragile, and the dialog only
    # ever renders the two lists side by side.
    imported_documents: list[ImportedDocumentDTO] = []
    skipped_documents: list[SkippedDocumentDTO] = []
    import_report_open: bool = False

    ############################################### DERIVED ###############################################

    @rx.var
    def is_upload_source(self) -> bool:
        """True when the selected source is the built-in upload provider.

        An upload has no source system to name a document in, so the dialog shows a drop zone instead
        of an id field.
        """
        return self.selected_source_type == UPLOAD_SOURCE_TYPE

    @rx.var
    def supports_tag_import(self) -> bool:
        """True when the selected source can be imported from by tag."""
        return self.selected_source_type == RESOURCE_SOURCE_TYPE

    @rx.var
    def is_tag_import_mode(self) -> bool:
        """True when the dialog is showing the import-by-tag form."""
        return self.supports_tag_import and self.add_mode == ADD_MODE_TAG

    @rx.var
    def has_rejections(self) -> bool:
        """True when the last attempt refused at least one document."""
        return len(self.rejections) > 0

    @rx.var
    def accepted_formats_label(self) -> str:
        """The formats and size cap, as one line for the drop zone."""
        return f"{ACCEPTED_EXTENSIONS_LABEL} — up to {MAX_DOCUMENT_SIZE_MB} MB"

    @rx.var
    def import_summary(self) -> str:
        """The one line that has to be honest: how many were added, how many were not."""
        added = len(self.imported_documents)
        skipped = len(self.skipped_documents)
        return f"{added} document(s) added, {skipped} skipped."

    @rx.var
    def has_imported_documents(self) -> bool:
        """True when the last import added at least one document."""
        return len(self.imported_documents) > 0

    @rx.var
    def has_skipped_documents(self) -> bool:
        """True when the last import skipped at least one candidate."""
        return len(self.skipped_documents) > 0

    ############################################### DIALOG ###############################################

    @rx.event
    def open_dialog(self) -> None:
        """Open the dialog, reading the available source types from the registry."""
        self.source_types = sorted(
            source.source_type for source in KnowledgeBaseDocumentSourceRegistry.all()
        )
        if self.selected_source_type not in self.source_types:
            self.selected_source_type = (
                UPLOAD_SOURCE_TYPE
                if UPLOAD_SOURCE_TYPE in self.source_types
                else (self.source_types[0] if self.source_types else "")
            )
        self.source_id = ""
        self.source_metadata_json = ""
        self.add_mode = ADD_MODE_SINGLE
        self.tag_key = ""
        self.tag_value = ""
        self.rejections = []
        self.dialog_open = True

    @rx.event
    def close_dialog(self) -> None:
        """Close the dialog."""
        self.dialog_open = False

    @rx.event
    def close_import_report(self) -> None:
        """Close the import report."""
        self.import_report_open = False

    @rx.event
    def set_selected_source_type(self, value: str) -> None:
        """Setter for the source-type select."""
        self.selected_source_type = value
        self.rejections = []
        # A source that cannot be imported by tag must not be left showing the tag form.
        if value != RESOURCE_SOURCE_TYPE:
            self.add_mode = ADD_MODE_SINGLE

    @rx.event
    def set_add_mode(self, value: str | list[str]) -> None:
        """Setter for the single-document / import-by-tag switch.

        The union is the segmented control's own signature: it is multi-select capable, so it types
        its ``on_change`` value as one item or a list. This one is single-select, so a list means the
        first item.
        """
        self.add_mode = value[0] if isinstance(value, list) else value
        self.rejections = []

    @rx.event
    def set_source_id(self, value: str) -> None:
        """Setter for the source-id field."""
        self.source_id = value

    @rx.event
    def set_source_metadata_json(self, value: str) -> None:
        """Setter for the optional provider-metadata field."""
        self.source_metadata_json = value

    @rx.event
    def set_tag_key(self, value: str) -> None:
        """Setter for the import tag key."""
        self.tag_key = value

    @rx.event
    def set_tag_value(self, value: str) -> None:
        """Setter for the import tag value."""
        self.tag_value = value

    ############################################### UPLOAD ###############################################

    @rx.event
    def handle_upload_progress(self, progress: dict[str, Any]) -> None:
        """Show the upload as running while the browser is still sending bytes."""
        if progress["progress"] < 1:
            self.is_uploading = True

    @rx.event
    async def handle_upload(
        self, files: list[rx.UploadFile]
    ) -> AsyncGenerator[rx.event.EventType, None]:
        """Add every uploaded file as a ``pending`` document, then index them in the background.

        Each file is admitted on its own: the loop keeps going after a rejection, and the reason is
        kept. The uploaded bytes *are* the snapshot, so nothing here contacts a source system.
        """
        if not files:
            self.is_uploading = False
            return

        knowledge_base_id = await self._get_knowledge_base_id()

        added_count = 0
        rejections: list[str] = []
        self.is_uploading = True
        try:
            main_state = await self.get_state(ReflexMainState)
            service = KnowledgeBaseService()
            for file in files:
                filename = file.name or "unnamed"
                content = await file.read()
                try:
                    with await main_state.authenticate_user():
                        service.add_uploaded_document(knowledge_base_id, filename, content)
                    added_count += 1
                except DOCUMENT_REJECTION_ERRORS as err:
                    # The admission check refused it, and said why. That reason is the whole value of
                    # this branch: a skipped file with no explanation reads as a success. No stack
                    # trace: nothing went wrong on the server, the file was simply not indexable.
                    rejections.append(f"{filename}: {err}")
                except Exception as err:
                    # Anything else — a provider error, a full disk — is reported the same way rather
                    # than aborting the batch. It is never swallowed, and unlike a rejection it is a
                    # server-side problem, so it is logged with its stack trace as well as shown.
                    Logger.log_exception_stack_trace(err)
                    rejections.append(f"{filename}: {err}")
        finally:
            self.is_uploading = False

        self.rejections = rejections

        # No ``rx.clear_selected_files`` here: in this Reflex version the front-end helper it calls
        # (``refs.__clear_selected_files``) is not defined, and the TypeError it throws aborts the
        # rest of the event queue — including the indexing event yielded below. The drop zone does not
        # render its selected-file list, so nothing needs clearing.
        for rejection in rejections:
            yield rx.toast.error(rejection, duration=8000)

        if added_count:
            yield rx.toast.success(
                f"{added_count} document(s) added, indexing them now.", duration=4000
            )
            if not rejections:
                # Nothing left to read in the dialog, so get out of the way of the table.
                self.dialog_open = False
            yield KnowledgeBaseDetailState.refresh_documents
            yield KnowledgeBaseDetailState.index_pending_documents

    ############################################### REGISTERED SOURCE ###############################################

    @rx.event
    async def add_from_source(self) -> AsyncGenerator[rx.event.EventType, None]:
        """Add a document from a registered source: fetch it, snapshot it, queue it for indexing.

        The provider is contacted here, which is why this can be slow or fail — and why its failure
        message is shown instead of a generic one.
        """
        knowledge_base_id = await self._get_knowledge_base_id()

        source_type = self.selected_source_type
        if not source_type:
            raise ReflexAppException("Choose a source type.")

        source_id = self.source_id.strip()
        if not source_id:
            raise ReflexAppException("The source document id is required.")

        source_metadata = self._parse_source_metadata()

        self.is_adding = True
        try:
            main_state = await self.get_state(ReflexMainState)
            with await main_state.authenticate_user():
                try:
                    document = KnowledgeBaseService().add_document(
                        knowledge_base_id=knowledge_base_id,
                        source_type=source_type,
                        source_id=source_id,
                        source_metadata=source_metadata,
                    )
                except DOCUMENT_REJECTION_ERRORS as err:
                    # Reported at add time, with the reason, while the user is still looking at the
                    # form.
                    self.rejections = [f"{source_id}: {err}"]
                    raise ReflexAppException(str(err)) from err
        finally:
            self.is_adding = False

        self.rejections = []
        self.dialog_open = False
        yield rx.toast.success(f"'{document.filename}' added, indexing it now.")
        yield KnowledgeBaseDetailState.refresh_documents
        yield KnowledgeBaseDetailState.index_pending_documents

    ############################################### IMPORT BY TAG ###############################################

    @rx.event(background=True)
    async def import_by_tag(self) -> None:
        """Add, snapshot and index every compatible resource carrying a tag.

        A background event because it is unbounded work: fifty resources means fifty fetches and fifty
        embedding runs, and the foreground event loop must stay free while it happens.

        It takes the detail page's indexing slot for the whole run. The service indexes each document
        as it adds it, so without the slot a pending sweep started by the page could pick the same
        document up and the two runs would race on its lease.

        Nothing is deleted, whatever the tag now matches — see
        :meth:`KnowledgeBaseService.import_documents`.
        """
        async with self:
            # Inside the lock, like every read of a var in a background handler.
            criteria = self._build_tag_criteria()
            main_state = await self.get_state(ReflexMainState)
            app_state = await self.get_state(KnowledgeBaseAppState)
            knowledge_base_id = await self._get_knowledge_base_id()
            detail_state = await self.get_state(KnowledgeBaseDetailState)
            if not detail_state.try_begin_indexing_run():
                raise ReflexAppException(INDEXING_IN_PROGRESS_MESSAGE)

            self.is_importing = True
            self.rejections = []
            try:
                # Inside the slot, so a failure to resolve the embedding configuration or to read the
                # knowledge base releases it instead of leaving the page indexing for good.
                with await main_state.authenticate_user():
                    knowledge_base = KnowledgeBaseService().get_knowledge_base_and_check(
                        knowledge_base_id
                    )
                engine = await app_state.build_engine(knowledge_base.instance_scope, main_state)
            except Exception:
                self.is_importing = False
                detail_state.end_indexing_run()
                raise

        try:
            service = KnowledgeBaseService()
            with await main_state.authenticate_user():
                report = service.import_documents(
                    knowledge_base_id=knowledge_base_id,
                    source_type=RESOURCE_SOURCE_TYPE,
                    criteria=criteria,
                    engine=engine,
                )
        finally:
            async with self:
                self.is_importing = False
                detail_state = await self.get_state(KnowledgeBaseDetailState)
                detail_state.end_indexing_run()
                await detail_state.reload_documents()

        async with self:
            self.imported_documents = report.added
            self.skipped_documents = report.skipped
            # The report replaces the form: everything the user has to read is in it, including the
            # skips, and a report behind an open dialog is a report nobody reads.
            self.dialog_open = False
            self.import_report_open = True

    ############################################### INTERNALS ###############################################

    def _build_tag_criteria(self) -> dict:
        """The criterion the import runs on, from the two tag fields.

        :raises ReflexAppException: if no tag key was given — importing with no criterion would make
                every resource in the lab a candidate
        """
        tag_key = self.tag_key.strip()
        if not tag_key:
            raise ReflexAppException("The tag key is required.")

        # An empty value matches every value of that key, which is the useful default for a tag used
        # as a flag rather than as a field.
        return {TAG_KEY_CRITERION: tag_key, TAG_VALUE_CRITERION: self.tag_value.strip()}

    async def _get_knowledge_base_id(self) -> str:
        """The knowledge base the dialog is adding to, read from the detail page's state.

        :raises ReflexAppException: if no knowledge base is open — adding a document to nothing would
                otherwise fail deep inside the service
        """
        detail_state = await self.get_state(KnowledgeBaseDetailState)
        knowledge_base_id = detail_state.get_loaded_knowledge_base_id()
        if not knowledge_base_id:
            raise ReflexAppException("Open a knowledge base before adding documents to it.")
        return knowledge_base_id

    def _parse_source_metadata(self) -> dict | None:
        """The optional provider metadata, as a dict.

        :raises ReflexAppException: if the text is not a JSON object — a provider reads keys out of
                it, so a JSON list or a bare string cannot be what was meant
        """
        raw = self.source_metadata_json.strip()
        if not raw:
            return None

        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError as err:
            raise ReflexAppException(f"The source metadata is not valid JSON: {err}") from err

        if not isinstance(parsed, dict):
            raise ReflexAppException("The source metadata must be a JSON object, for example {}.")
        return parsed
