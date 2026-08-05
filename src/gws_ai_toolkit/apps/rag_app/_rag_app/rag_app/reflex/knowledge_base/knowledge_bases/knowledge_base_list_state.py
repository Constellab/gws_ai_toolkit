"""State of the knowledge-base list page: list, create, edit, open, delete.

A few things are worth spelling out.

**This state also drives the detail page's actions menu.** The edit dialog and the delete confirmation
declared here are rendered on both ``knowledge_base_list_component`` and ``knowledge_base_detail_component``
(behind ``knowledge_base_actions_menu``, shared by the two), so a knowledge base can be renamed or
deleted from wherever it is being looked at. That is why ``open_edit_dialog`` reads the row fresh from
the service instead of from ``knowledge_bases``: the detail page never populates that list. It is also
why ``save_knowledge_base`` and ``delete_knowledge_base`` reach into :class:`KnowledgeBaseDetailState` —
a save patches its cached copy in place so a renamed knowledge base does not look stale on its own
detail page, and a delete redirects away from it, since there is nothing left there to show.

**Create and edit are the same dialog.** ``_editing_knowledge_base`` decides which of the two a save
performs. Unlike the chat-profile dialog this mirrors, the edit form does not expose every field a
knowledge base has — chunking policy and instance scope stay create-only (see below) — so
``_editing_knowledge_base`` also carries those fields, read straight off the row being edited, so a
save cannot regress them back to defaults.

**Deleting a knowledge base needs an engine**, because the chunks go first (a row deleted before its
chunks leaves vectors that retrieval can still return and that nothing points at). The engine is
built for the deleted knowledge base's *own* ``instance_scope``, read off the row rather than assumed
to be the default — a knowledge base in another scope would otherwise have its chunks left behind in
the instance it actually lives in.

**A name clash is a user-facing error, not a bug.** ``KnowledgeBaseService`` raises
``KnowledgeBaseNameAlreadyUsedError`` with a message written for a user, so it is re-raised as a
``ReflexAppException`` and lands in a toast; everything else is left to the global handler installed
by ``register_gws_reflex_app``.

A knowledge base is always created in ``DEFAULT_INSTANCE_SCOPE``. The scope decides which vector space
holds the chunks, so a typo in a free-text field would silently create a knowledge base in an instance
nothing else addresses; choosing another scope belongs to the app's configuration, not to a create
form. The scope a knowledge base lives in is still *shown*, because it explains what a retrieval can
reach. The chunking policy is likewise create-only: a new chunk size only affects documents indexed
after the change, so changing it on an existing knowledge base would misleadingly suggest its already
indexed documents were reprocessed.
"""

from collections.abc import AsyncGenerator

import reflex as rx
from gws_ai_toolkit.models.knowledge_base.knowledge_base_dto import (
    KnowledgeBaseDTO,
    SaveKnowledgeBaseDTO,
)
from gws_ai_toolkit.models.knowledge_base.knowledge_base_service import (
    KnowledgeBaseNameAlreadyUsedError,
    KnowledgeBaseService,
)
from gws_ai_toolkit.rag.knowledge_base.knowledge_base_config import (
    DEFAULT_CHUNK_OVERLAP,
    DEFAULT_CHUNK_SIZE,
)
from gws_ai_toolkit.rag.knowledge_base.knowledge_base_storage import DEFAULT_INSTANCE_SCOPE
from gws_reflex_main import ReflexAppException, ReflexMainState

from ..core.form_parsing import parse_positive_int
from ..core.knowledge_base_app_state import KnowledgeBaseAppState
from .knowledge_base_detail_state import KnowledgeBaseDetailState

KNOWLEDGE_BASES_ROUTE = "/kb/bases"


class KnowledgeBaseListState(rx.State):
    """The knowledge bases of this lab, and the create / delete actions on them.

    ``knowledge_bases`` holds :class:`KnowledgeBaseDTO` values, never Peewee rows: a row carries a
    live database connection and lazy foreign keys, and this list is serialised to the browser on
    every event.
    """

    knowledge_bases: list[KnowledgeBaseDTO] = []
    is_loading: bool = False

    # The edit dialog. A ``None`` ``_editing_knowledge_base`` means "create"; otherwise the dialog is
    # editing that knowledge base, and its fields the form doesn't expose are read back off it on save.
    # The numeric fields are kept as strings because that is what an ``rx.input`` produces; they are
    # parsed once, on submit, where a bad value can be named and reported.
    dialog_open: bool = False
    is_saving: bool = False
    _editing_knowledge_base: KnowledgeBaseDTO | None = None
    form_name: str = ""
    form_description: str = ""
    form_chunk_size: str = str(DEFAULT_CHUNK_SIZE)
    form_chunk_overlap: str = str(DEFAULT_CHUNK_OVERLAP)

    # Id of the knowledge base a row action is working on, so its own row can show the spinner rather
    # than the whole table going busy.
    busy_knowledge_base_id: str = ""

    # The knowledge base whose delete-confirmation dialog is open, or "" for none. Controlled rather
    # than trigger-driven: the button that opens it is a menu item, not a stand-alone button a Radix
    # alert-dialog trigger can wrap.
    delete_dialog_knowledge_base_id: str = ""

    ############################################### READ ###############################################

    @rx.var
    def has_knowledge_bases(self) -> bool:
        """True when there is at least one knowledge base to show."""
        return len(self.knowledge_bases) > 0

    @rx.var
    def dialog_title(self) -> str:
        """Title of the dialog, which is the one place create and edit look different."""
        return "Edit knowledge base" if self._editing_knowledge_base else "New knowledge base"

    @rx.var
    def is_editing_knowledge_base(self) -> bool:
        """True when the dialog is editing a knowledge base rather than creating one.

        The component needs this as a plain var: ``_editing_knowledge_base`` is backend-only and
        cannot be read from an ``rx.cond``, but the chunking fields must hide once there is a knowledge
        base being edited.
        """
        return self._editing_knowledge_base is not None

    @rx.event
    async def load_knowledge_bases(self) -> None:
        """Load the knowledge bases. Bound to the page's ``on_load``."""
        self.is_loading = True
        try:
            await self._reload_knowledge_bases()
        finally:
            self.is_loading = False

    ############################################### DIALOG ###############################################

    @rx.event
    def open_create_dialog(self) -> None:
        """Open the dialog on a blank create form."""
        self._editing_knowledge_base = None
        self.form_name = ""
        self.form_description = ""
        self.form_chunk_size = str(DEFAULT_CHUNK_SIZE)
        self.form_chunk_overlap = str(DEFAULT_CHUNK_OVERLAP)
        self.dialog_open = True

    @rx.event
    async def open_edit_dialog(self, knowledge_base_id: str) -> None:
        """Open the dialog on an existing knowledge base's name and description.

        Read fresh from the service rather than from ``knowledge_bases``: this also opens from the
        detail page's actions menu, and that page never loads the list.

        :raises ReflexAppException: if the knowledge base no longer exists
        """
        main_state = await self.get_state(ReflexMainState)
        with await main_state.authenticate_user():
            knowledge_base = KnowledgeBaseService().get_knowledge_base(knowledge_base_id)
        if knowledge_base is None:
            raise ReflexAppException("This knowledge base no longer exists. Refresh the page.")

        self._editing_knowledge_base = knowledge_base.to_dto()
        self.form_name = knowledge_base.name
        self.form_description = knowledge_base.description
        self.dialog_open = True

    @rx.event
    def close_dialog(self) -> None:
        """Close the dialog, discarding whatever was typed."""
        self.dialog_open = False

    @rx.event
    def set_form_name(self, value: str) -> None:
        """Setter for the name field."""
        self.form_name = value

    @rx.event
    def set_form_description(self, value: str) -> None:
        """Setter for the description field."""
        self.form_description = value

    @rx.event
    def set_form_chunk_size(self, value: str) -> None:
        """Setter for the chunk-size field. Only shown while creating."""
        self.form_chunk_size = value

    @rx.event
    def set_form_chunk_overlap(self, value: str) -> None:
        """Setter for the chunk-overlap field. Only shown while creating."""
        self.form_chunk_overlap = value

    ############################################### SAVE ###############################################

    @rx.event
    async def save_knowledge_base(self) -> AsyncGenerator[rx.event.EventType, None]:
        """Create or update the knowledge base the dialog is open on.

        A freshly created knowledge base is opened straight away: it is empty and useless, and the
        next thing anyone wants is the add-document button on its detail page. An update stays
        wherever it was opened from — the list reloads its row, and the detail page's own cached copy
        is patched in place so a renamed knowledge base does not look stale on its own page.

        :raises ReflexAppException: if the form is incomplete, or the name is taken
        """
        name = self.form_name.strip()
        if not name:
            raise ReflexAppException("A knowledge base needs a name.")

        editing = self._editing_knowledge_base
        save_dto = SaveKnowledgeBaseDTO(
            name=name,
            description=self.form_description.strip(),
            instance_scope=editing.instance_scope if editing else DEFAULT_INSTANCE_SCOPE,
            chunk_size=(
                editing.chunk_size
                if editing
                else parse_positive_int(self.form_chunk_size, "Chunk size")
            ),
            chunk_overlap=(
                editing.chunk_overlap
                if editing
                else parse_positive_int(self.form_chunk_overlap, "Chunk overlap", allow_zero=True)
            ),
            sync_source_type=editing.sync_source_type if editing else None,
            sync_config=editing.sync_config if editing else None,
        )

        self.is_saving = True
        try:
            main_state = await self.get_state(ReflexMainState)
            service = KnowledgeBaseService()
            with await main_state.authenticate_user():
                try:
                    if editing:
                        knowledge_base = service.update_knowledge_base(editing.id, save_dto)
                    else:
                        knowledge_base = service.create_knowledge_base(save_dto)
                except KnowledgeBaseNameAlreadyUsedError as err:
                    # The service wrote this message for a user; a toast is where it belongs.
                    raise ReflexAppException(str(err)) from err
        finally:
            self.is_saving = False

        self.dialog_open = False
        if editing:
            await self._reload_knowledge_bases()
            detail_state = await self.get_state(KnowledgeBaseDetailState)
            if detail_state.knowledge_base and detail_state.knowledge_base.id == editing.id:
                detail_state.knowledge_base = knowledge_base.to_dto()
            yield rx.toast.success(f"Knowledge base '{knowledge_base.name}' updated.")
        else:
            yield rx.toast.success(f"Knowledge base '{knowledge_base.name}' created.")
            yield rx.redirect(f"{KNOWLEDGE_BASES_ROUTE}/{knowledge_base.id}")

    ############################################### DELETE ###############################################

    @rx.event
    def set_delete_dialog_open(self, is_open: bool, knowledge_base_id: str) -> None:
        """Open or close one knowledge base's delete-confirmation dialog.

        Bound both to the menu item that opens it and to the dialog's own ``on_open_change``, so
        Radix's own ways of closing it — Escape, an overlay click, the Cancel or Delete button —
        clear the id the same way opening it set it.
        """
        self.delete_dialog_knowledge_base_id = knowledge_base_id if is_open else ""

    @rx.event(background=True)
    async def delete_knowledge_base(
        self, knowledge_base_id: str
    ) -> AsyncGenerator[rx.event.EventType, None]:
        """Delete a knowledge base: its chunks, its snapshots and its rows.

        A background event because deleting the chunks takes the instance's write lock and rewrites a
        LanceDB table, which has no business happening inside a foreground event. If its own detail
        page is open when this runs, that page is left with nothing to show, so it is redirected away.

        Confirmation is the caller's: the button that reaches this sits behind an alert dialog.
        """
        service = KnowledgeBaseService()
        async with self:
            self.busy_knowledge_base_id = knowledge_base_id

        # Everything after the flag is set lives in the ``try``, including the lookups and the engine:
        # resolving credentials or reading the row can raise, and a spinner left on a row nothing is
        # working on would be a lie the user cannot clear.
        try:
            async with self:
                main_state = await self.get_state(ReflexMainState)
                app_state = await self.get_state(KnowledgeBaseAppState)
                with await main_state.authenticate_user():
                    knowledge_base = service.get_knowledge_base_and_check(knowledge_base_id)
                    name = knowledge_base.name
                    instance_scope = knowledge_base.instance_scope
                    # The scope of *this* knowledge base, not the default: its chunks live nowhere
                    # else. Built inside the lock because it needs ``get_state``, which a background
                    # handler's proxy refuses outside its context manager; used once below, then
                    # dropped. Never kept on the state.
                    engine = await app_state.build_engine(instance_scope, main_state)

            with await main_state.authenticate_user():
                service.delete_knowledge_base(knowledge_base_id, engine)
        finally:
            async with self:
                self.busy_knowledge_base_id = ""

        async with self:
            await self._reload_knowledge_bases()
            detail_state = await self.get_state(KnowledgeBaseDetailState)
            showing_deleted = (
                detail_state.knowledge_base is not None
                and detail_state.knowledge_base.id == knowledge_base_id
            )

        yield rx.toast.success(f"Knowledge base '{name}' deleted.")
        if showing_deleted:
            yield rx.redirect(KNOWLEDGE_BASES_ROUTE)

    ############################################### INTERNALS ###############################################

    async def _reload_knowledge_bases(self) -> None:
        """Re-read the list. Callable from the backend, unlike the event handlers above."""
        main_state = await self.get_state(ReflexMainState)
        with await main_state.authenticate_user():
            knowledge_bases = KnowledgeBaseService().get_all_knowledge_bases()
        self.knowledge_bases = [knowledge_base.to_dto() for knowledge_base in knowledge_bases]
