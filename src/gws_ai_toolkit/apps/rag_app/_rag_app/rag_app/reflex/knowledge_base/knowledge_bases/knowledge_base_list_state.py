"""State of the knowledge-base list page: list, create, open, delete.

Two things are worth spelling out.

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
reach.
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

KNOWLEDGE_BASES_ROUTE = "/kb/bases"


class KnowledgeBaseListState(rx.State):
    """The knowledge bases of this lab, and the create / delete actions on them.

    ``knowledge_bases`` holds :class:`KnowledgeBaseDTO` values, never Peewee rows: a row carries a
    live database connection and lazy foreign keys, and this list is serialised to the browser on
    every event.
    """

    knowledge_bases: list[KnowledgeBaseDTO] = []
    is_loading: bool = False

    # Create dialog. The numeric fields are kept as strings because that is what an ``rx.input``
    # produces; they are parsed once, on submit, where a bad value can be named and reported.
    create_dialog_open: bool = False
    is_creating: bool = False
    new_name: str = ""
    new_description: str = ""
    new_chunk_size: str = str(DEFAULT_CHUNK_SIZE)
    new_chunk_overlap: str = str(DEFAULT_CHUNK_OVERLAP)

    # Id of the knowledge base a row action is working on, so its own row can show the spinner rather
    # than the whole table going busy.
    busy_knowledge_base_id: str = ""

    ############################################### READ ###############################################

    @rx.var
    def has_knowledge_bases(self) -> bool:
        """True when there is at least one knowledge base to show."""
        return len(self.knowledge_bases) > 0

    @rx.event
    async def load_knowledge_bases(self) -> None:
        """Load the knowledge bases. Bound to the page's ``on_load``."""
        self.is_loading = True
        try:
            await self._reload_knowledge_bases()
        finally:
            self.is_loading = False

    ############################################### CREATE ###############################################

    @rx.event
    def open_create_dialog(self) -> None:
        """Open the create dialog on a blank form."""
        self.new_name = ""
        self.new_description = ""
        self.new_chunk_size = str(DEFAULT_CHUNK_SIZE)
        self.new_chunk_overlap = str(DEFAULT_CHUNK_OVERLAP)
        self.create_dialog_open = True

    @rx.event
    def close_create_dialog(self) -> None:
        """Close the create dialog, discarding whatever was typed."""
        self.create_dialog_open = False

    @rx.event
    def set_new_name(self, value: str) -> None:
        """Setter for the name field of the create form."""
        self.new_name = value

    @rx.event
    def set_new_description(self, value: str) -> None:
        """Setter for the description field of the create form."""
        self.new_description = value

    @rx.event
    def set_new_chunk_size(self, value: str) -> None:
        """Setter for the chunk-size field of the create form."""
        self.new_chunk_size = value

    @rx.event
    def set_new_chunk_overlap(self, value: str) -> None:
        """Setter for the chunk-overlap field of the create form."""
        self.new_chunk_overlap = value

    @rx.event
    async def create_knowledge_base(self) -> AsyncGenerator[rx.event.EventType, None]:
        """Create a knowledge base from the dialog's fields, then open it.

        Opening it straight away is deliberate: an empty knowledge base is useless, and the next
        thing anyone wants is the add-document button on its detail page.

        :raises ReflexAppException: if the form is incomplete, or the name is taken
        """
        name = self.new_name.strip()
        if not name:
            raise ReflexAppException("A knowledge base needs a name.")

        save_dto = SaveKnowledgeBaseDTO(
            name=name,
            description=self.new_description.strip(),
            instance_scope=DEFAULT_INSTANCE_SCOPE,
            chunk_size=parse_positive_int(self.new_chunk_size, "Chunk size"),
            chunk_overlap=parse_positive_int(
                self.new_chunk_overlap, "Chunk overlap", allow_zero=True
            ),
        )

        self.is_creating = True
        try:
            main_state = await self.get_state(ReflexMainState)
            with await main_state.authenticate_user():
                try:
                    knowledge_base = KnowledgeBaseService().create_knowledge_base(save_dto)
                except KnowledgeBaseNameAlreadyUsedError as err:
                    # The service wrote this message for a user; a toast is where it belongs.
                    raise ReflexAppException(str(err)) from err
        finally:
            self.is_creating = False

        self.create_dialog_open = False
        yield rx.toast.success(f"Knowledge base '{knowledge_base.name}' created.")
        yield rx.redirect(f"{KNOWLEDGE_BASES_ROUTE}/{knowledge_base.id}")

    ############################################### DELETE ###############################################

    @rx.event(background=True)
    async def delete_knowledge_base(
        self, knowledge_base_id: str
    ) -> AsyncGenerator[rx.event.EventType, None]:
        """Delete a knowledge base: its chunks, its snapshots and its rows.

        A background event because deleting the chunks takes the instance's write lock and rewrites a
        LanceDB table, which has no business happening inside a foreground event.

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

        yield rx.toast.success(f"Knowledge base '{name}' deleted.")

    ############################################### INTERNALS ###############################################

    async def _reload_knowledge_bases(self) -> None:
        """Re-read the list. Callable from the backend, unlike the event handlers above."""
        main_state = await self.get_state(ReflexMainState)
        with await main_state.authenticate_user():
            knowledge_bases = KnowledgeBaseService().get_all_knowledge_bases()
        self.knowledge_bases = [knowledge_base.to_dto() for knowledge_base in knowledge_bases]
