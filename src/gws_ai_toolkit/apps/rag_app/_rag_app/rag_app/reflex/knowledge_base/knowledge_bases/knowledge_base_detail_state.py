"""State of one knowledge base's page: its documents, and what can be done to each of them.

Three decisions shape this file.

**Stale leases are reclaimed on load.** Indexing runs in a background event whose process is killed on
idle, so a row can be left ``indexing`` by a run that no longer exists. ``reclaim_stale_leases()`` is
called every time the page loads, which turns such a row into a retryable ``error`` carrying
``INTERRUPTED_INDEXING_MESSAGE`` — the table then shows *interrupted*, not a spinner that never stops.
``KnowledgeBaseDocument.to_dto()`` already reports an over-age lease as ``error`` even before a
reclaim, so the two agree; the reclaim is what makes the row actually retryable.

**The engine is built per operation and never stored.** It holds a LanceDB connection and takes an
``fcntl`` lock on each call; a Reflex state is serialised between events, and a background event's
process can die at any point. ``KnowledgeBaseAppState.build_engine`` is therefore called inside each
handler, and the result goes out of scope with it. Opening a local directory is cheap.

**Indexing refreshes the table after every document**, rather than once at the end of a batch: the
whole point of a background event here is that a row reaches ``done`` with its chunk count without
anyone pressing refresh. The pending list is re-read after every pass, so a document uploaded while a
run was working is picked up by that same run instead of being left ``pending`` with nothing to retry
it.
"""

from collections.abc import AsyncGenerator

import reflex as rx
from gws_ai_toolkit.models.knowledge_base.knowledge_base_dto import (
    DocumentIndexStatus,
    KnowledgeBaseDocumentDTO,
    KnowledgeBaseDTO,
)
from gws_ai_toolkit.models.knowledge_base.knowledge_base_service import KnowledgeBaseService
from gws_ai_toolkit.rag.knowledge_base.knowledge_base_engine import KnowledgeBaseEngine
from gws_reflex_main import ReflexAppException, ReflexMainState

from ..core.knowledge_base_app_state import KnowledgeBaseAppState
from ..core.knowledge_base_errors import DOCUMENT_REJECTION_ERRORS

# Name of the dynamic segment of ``/kb/bases/[knowledge_base_id]``. Reflex exposes it as a var of the
# same name on every state, which is also why no state here may declare a var called this.
KNOWLEDGE_BASE_ID_ROUTE_ARG = "knowledge_base_id"

# What a caller is told when this page's single indexing slot is already taken. Shared with the
# add-document dialog, whose bulk import takes the same slot.
INDEXING_IN_PROGRESS_MESSAGE = (
    "An indexing run is already in progress for this knowledge base. Wait for it to finish, then try "
    "again."
)


class KnowledgeBaseDetailState(rx.State):
    """One knowledge base, its documents, and the per-document operations.

    ``documents`` holds :class:`KnowledgeBaseDocumentDTO` values. That matters beyond the usual
    row-versus-DTO rule: the DTO deliberately omits ``snapshot_path``, and this list is serialised to
    the browser.
    """

    knowledge_base: KnowledgeBaseDTO | None = None
    documents: list[KnowledgeBaseDocumentDTO] = []

    # The id the page was loaded with, kept so background events do not have to re-read the router.
    # A backend var: nothing in the UI reads it, and the id is already in the URL. Not called
    # ``knowledge_base_id`` either — that name belongs to the dynamic route var.
    _loaded_knowledge_base_id: str = ""

    is_loading: bool = False
    # True while an indexing run owns this page. One run at a time, so two runs cannot index the same
    # document concurrently and race on its lease.
    is_indexing: bool = False
    # The document a per-row action is working on, so only its own row shows a spinner.
    busy_document_id: str = ""
    # The document whose delete-confirmation dialog is open, or "" for none. Controlled rather than
    # trigger-driven: the button that opens it is a menu item, not a stand-alone button a Radix
    # alert-dialog trigger can wrap.
    delete_dialog_document_id: str = ""

    ############################################### DERIVED ###############################################

    @rx.var
    def has_documents(self) -> bool:
        """True when the knowledge base holds at least one document."""
        return len(self.documents) > 0

    @rx.var
    def document_count(self) -> int:
        """How many documents the knowledge base holds."""
        return len(self.documents)

    @rx.var
    def total_chunk_count(self) -> int:
        """Total chunks across the documents.

        Counted from the rows rather than from the engine: the row's ``chunk_count`` is what the last
        successful indexing run wrote, and a cheap count is worth more here than a query per page
        load.
        """
        return sum(document.chunk_count for document in self.documents)

    @rx.var
    def chunk_config_label(self) -> str:
        """The knowledge base's chunking policy, as one line of text."""
        if self.knowledge_base is None:
            return ""
        return (
            f"{self.knowledge_base.chunk_size} tokens / "
            f"{self.knowledge_base.chunk_overlap} overlap"
        )

    ############################################### LOAD ###############################################

    @rx.event
    async def load_knowledge_base(self) -> AsyncGenerator[rx.event.EventType, None]:
        """Load the knowledge base named by the route, then index whatever is still pending.

        Bound to the page's ``on_load``. Reclaiming stale leases happens first, so a run killed by an
        idle app is already reported as interrupted by the time the table is rendered.
        """
        knowledge_base_id = self._get_route_knowledge_base_id()
        if not knowledge_base_id:
            self.knowledge_base = None
            self.documents = []
            return

        self._loaded_knowledge_base_id = knowledge_base_id
        self.is_loading = True
        try:
            main_state = await self.get_state(ReflexMainState)
            service = KnowledgeBaseService()
            with await main_state.authenticate_user():
                # Before reading the documents, so an abandoned run shows as interrupted rather than
                # as a document that has been "indexing" since yesterday.
                service.reclaim_stale_leases()
                knowledge_base = service.get_knowledge_base_and_check(knowledge_base_id)
                self.knowledge_base = knowledge_base.to_dto()
                self.documents = [
                    document.to_dto() for document in service.get_documents(knowledge_base_id)
                ]
        finally:
            self.is_loading = False

        if any(
            document.index_status == DocumentIndexStatus.PENDING.value
            for document in self.documents
        ):
            # A foreground handler may chain a sibling event; a background one may not.
            yield KnowledgeBaseDetailState.index_pending_documents

    @rx.event
    async def refresh_documents(self) -> None:
        """Re-read the document table, reclaiming stale leases on the way.

        This is the manual refresh button. It is not what makes indexing visible — that happens on
        its own — but it is what a user reaches for after an external change, and it is the honest
        answer to a row that has been ``indexing`` too long.
        """
        if not self._loaded_knowledge_base_id:
            return

        main_state = await self.get_state(ReflexMainState)
        with await main_state.authenticate_user():
            KnowledgeBaseService().reclaim_stale_leases()
        await self._reload_documents()

    ############################################### INDEX ###############################################

    @rx.event(background=True)
    async def index_pending_documents(self) -> None:
        """Index every ``pending`` document of this knowledge base, refreshing the table as it goes.

        The work list is read from the database rather than from ``self.documents``, and re-read after
        every pass: an upload that arrives while this run is working must not be missed. Called again
        while a run is in progress, this returns quietly — that run will pick the new documents up.
        """
        await self._index_documents(None)

    @rx.event(background=True)
    async def reindex_document(self, document_id: str) -> None:
        """Re-index one document from its stored snapshot.

        Safe to retry at any status: the engine deletes the document's chunks before writing the new
        ones, so no run can leave duplicates. This never contacts the source system — use *refresh*
        for that.
        """
        await self._index_documents([document_id])

    ############################################### REFRESH FROM SOURCE ###############################################

    @rx.event(background=True)
    async def refresh_document_from_source(
        self, document_id: str
    ) -> AsyncGenerator[rx.event.EventType, None]:
        """Re-fetch a document from its source, replace its snapshot, then re-index it.

        A source that cannot be re-fetched — an upload, whose bytes *are* its snapshot — says so, and
        that message is shown rather than swallowed: it tells the user to upload the new version
        instead.

        **A document whose content did not change is not re-indexed.** The version marker is a content
        hash, so a note someone opened and saved without editing comes back identical, and the honest
        answer is to say nothing changed rather than to pay for embedding the same text again.
        """
        async with self:
            self.busy_document_id = document_id

        try:
            async with self:
                main_state = await self.get_state(ReflexMainState)

            service = KnowledgeBaseService()
            with await main_state.authenticate_user():
                try:
                    refresh = service.refresh_document(document_id)
                except DOCUMENT_REJECTION_ERRORS as err:
                    # Every one of these carries a message written for a user: an upload cannot be
                    # re-fetched, a provider is no longer installed, the new version is of a format
                    # or a size that cannot be indexed.
                    raise ReflexAppException(str(err)) from err
            filename = refresh.document.filename
        finally:
            async with self:
                self.busy_document_id = ""

        async with self:
            await self._reload_documents()

        if not refresh.content_changed:
            yield rx.toast.info(
                f"'{filename}' is unchanged in its source, so nothing was re-indexed.",
                duration=6000,
            )
            return

        yield rx.toast.success(f"'{filename}' re-fetched from its source, re-indexing it.")

        # An inline await rather than ``yield KnowledgeBaseDetailState.reindex_document``: chaining a
        # sibling event from a background handler can raise on an already-finalised EventFuture.
        await self._index_documents([document_id])

    ############################################### DELETE ###############################################

    @rx.event
    def set_delete_dialog_open(self, is_open: bool, document_id: str) -> None:
        """Open or close one document's delete-confirmation dialog.

        Bound both to the menu item that opens it and to the dialog's own ``on_open_change``, so
        Radix's own ways of closing it — Escape, an overlay click, the Cancel or Delete button —
        clear the id the same way opening it set it.
        """
        self.delete_dialog_document_id = document_id if is_open else ""

    @rx.event(background=True)
    async def delete_document(self, document_id: str) -> AsyncGenerator[rx.event.EventType, None]:
        """Delete a document: its chunks, its snapshot and its row.

        Confirmation is the caller's: the button that reaches this sits behind an alert dialog.
        """
        service = KnowledgeBaseService()
        async with self:
            self.busy_document_id = document_id

        # Everything after the flag is set lives in the ``try``, including the lookups and the engine:
        # resolving the embedding configuration or reading the row can raise, and a row left spinning
        # on an operation that never started is a lie the user cannot clear.
        try:
            async with self:
                main_state = await self.get_state(ReflexMainState)
                app_state = await self.get_state(KnowledgeBaseAppState)
                instance_scope = self._get_instance_scope()
                with await main_state.authenticate_user():
                    filename = service.get_document_and_check(document_id).filename
                # Inside the lock because building it needs ``get_state``; used once below, then
                # dropped.
                engine = await app_state.build_engine(instance_scope, main_state)

            with await main_state.authenticate_user():
                service.delete_document(document_id, engine)
        finally:
            async with self:
                self.busy_document_id = ""

        async with self:
            await self._reload_documents()

        yield rx.toast.success(f"'{filename}' deleted.")

    ############################################### INTERNALS ###############################################

    def get_loaded_knowledge_base_id(self) -> str:
        """The knowledge base this page was loaded with, for a sibling state to read.

        The var behind it is backend-only — nothing in the UI needs it, and the id is already in the
        URL — so this is how the add-document dialog asks which knowledge base it is adding to.
        """
        return self._loaded_knowledge_base_id

    def try_begin_indexing_run(self) -> bool:
        """Claim this page's single indexing slot, or report that it is taken.

        Not an event: the caller is either this state or the add-document dialog, and both call it
        from the backend while holding their own state lock. The slot exists so two runs cannot index
        the same document concurrently and race on its lease — a bulk import indexes as it adds, so it
        has to take the same slot as the pending sweep.

        :return: True if the caller now owns the slot and must release it when done
        """
        if self.is_indexing:
            return False
        self.is_indexing = True
        return True

    def end_indexing_run(self) -> None:
        """Release this page's indexing slot. Always call it in a ``finally``."""
        self.is_indexing = False

    async def reload_documents(self) -> None:
        """Re-read the document table, for a sibling state that has just changed it.

        The bulk import lives on the add-document dialog's state, so it needs a way to refresh this
        table that is not an event: a background handler must not chain a sibling event.
        """
        await self._reload_documents()

    async def _index_documents(self, document_ids: list[str] | None) -> None:
        """Index documents one at a time, refreshing the table after each.

        :param document_ids: the documents to index, or ``None`` to sweep everything still
                             ``pending`` — re-read from the database after every pass, so a document
                             uploaded while this run was working is indexed by this run
        :raises ReflexAppException: if a named document is asked for while a run is in progress; two
                runs on the same document would race on its lease, and refusing is more honest than
                queueing silently
        """
        async with self:
            knowledge_base_id = self._loaded_knowledge_base_id
            if not knowledge_base_id:
                return
            if not self.try_begin_indexing_run():
                if document_ids is None:
                    # The pending sweep. The run already going re-reads the pending documents after
                    # every pass, so whatever triggered this is in its work list already. Refusing
                    # here would leave a freshly uploaded document ``pending`` with nothing to retry
                    # it — the row would never reach ``done`` without a manual re-index.
                    return
                raise ReflexAppException(INDEXING_IN_PROGRESS_MESSAGE)

        # From here on the flag is set, so everything — including resolving the embedding
        # configuration, which can raise on missing credentials or a manifest mismatch — has to sit
        # inside the ``try``. Otherwise a failure before the first document would leave the page
        # ``is_indexing`` for good, with every row's re-index and refresh button disabled.
        try:
            service = KnowledgeBaseService()
            async with self:
                main_state = await self.get_state(ReflexMainState)
                app_state = await self.get_state(KnowledgeBaseAppState)
                with await main_state.authenticate_user():
                    knowledge_base = service.get_knowledge_base_and_check(knowledge_base_id)
                # One engine for the whole run: still one operation, still nothing stored on the
                # state. Built inside the lock because it needs ``get_state``, which a background
                # handler's proxy refuses outside its context manager; the slow part — embedding and
                # writing chunks — happens below, outside the lock.
                engine = await app_state.build_engine(knowledge_base.instance_scope, main_state)

            with await main_state.authenticate_user():
                if document_ids is not None:
                    await self._index_batch(document_ids, service, engine)
                else:
                    # Sweep until nothing pending is left. ``attempted`` is what makes this
                    # terminate: a document is only ever picked up once per run, whatever status the
                    # service leaves on its row.
                    attempted: set[str] = set()
                    while True:
                        pending_ids = [
                            document.id
                            for document in service.get_documents_to_index(knowledge_base_id)
                            if document.id not in attempted
                        ]
                        if not pending_ids:
                            break
                        attempted.update(pending_ids)
                        await self._index_batch(pending_ids, service, engine)
        finally:
            async with self:
                self.end_indexing_run()

    async def _index_batch(
        self, document_ids: list[str], service: KnowledgeBaseService, engine: KnowledgeBaseEngine
    ) -> None:
        """Index the given documents in order, refreshing the table after each one.

        :param document_ids: the documents to index, in the order they should be indexed
        :param service: the service to index through, already inside an authenticated context
        :param engine: the engine for this knowledge base's instance scope
        """
        for document_id in document_ids:
            # The service records a failure on the row (status ``error`` plus the message) instead of
            # raising, so one bad document does not abandon the rest of the batch — and the reason is
            # on screen either way.
            service.index_document(document_id, engine)
            async with self:
                await self._reload_documents()

    async def _reload_documents(self) -> None:
        """Re-read the document rows into DTOs. Callable from the backend, unlike the events above."""
        if not self._loaded_knowledge_base_id:
            return
        main_state = await self.get_state(ReflexMainState)
        with await main_state.authenticate_user():
            documents = KnowledgeBaseService().get_documents(self._loaded_knowledge_base_id)
        self.documents = [document.to_dto() for document in documents]

    def _get_instance_scope(self) -> str:
        """The loaded knowledge base's instance scope.

        :raises ReflexAppException: if no knowledge base is loaded — an engine built for the wrong
                scope would address another vector space, so guessing a default is not an option
        """
        if self.knowledge_base is None:
            raise ReflexAppException("No knowledge base is loaded.")
        return self.knowledge_base.instance_scope

    def _get_route_knowledge_base_id(self) -> str:
        """The knowledge-base id from ``/kb/bases/[knowledge_base_id]``.

        Read through ``getattr``: the var is created by Reflex when the route is registered, not
        declared on this class, so a direct attribute access would be a lie to the reader.
        """
        return str(getattr(self, KNOWLEDGE_BASE_ID_ROUTE_ARG, "") or "")
