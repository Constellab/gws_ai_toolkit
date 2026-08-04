"""How the app reaches the embedded knowledge-base stack — and what it refuses to keep.

Every knowledge-base operation needs a :class:`KnowledgeBaseEngine`, and an engine holds a LanceDB
connection plus an ``fcntl`` lock on the instance directory. **Neither may live on a Reflex state**:
a state is pickled between events (and pushed to the frontend delta-by-delta), a background event
runs in a process that is killed on idle, and a lock held across events is a lock nothing will ever
release. So this state exposes *builders*, never a cached engine — see :meth:`build_engine`. Opening
a local LanceDB directory is a directory read, which is why building one per operation is the cheap
option rather than the careful one.

The embedding configuration is resolved from the app's params on every call for the same reason: the
API key is a secret that has no business sitting in a serialised state, and the credentials lookup
is a single indexed query.
"""

import reflex as rx
from gws_ai_toolkit.models.knowledge_base.knowledge_base_service import KnowledgeBaseService
from gws_ai_toolkit.rag.knowledge_base.knowledge_base_config import (
    DEFAULT_OPENAI_EMBEDDING_DIMENSIONS,
    DEFAULT_OPENAI_EMBEDDING_MODEL,
    EmbeddingConfig,
    EmbeddingProvider,
)
from gws_ai_toolkit.rag.knowledge_base.knowledge_base_credentials import resolve_openai_api_key
from gws_ai_toolkit.rag.knowledge_base.knowledge_base_engine import KnowledgeBaseEngine
from gws_reflex_main import ReflexMainState

# App params, read the way ``core/app_config_state.py`` reads its own: through
# ``ReflexMainState.get_params()``, so the generator task and ``dev_config.json`` configure the same
# keys. All four are optional — the defaults are the ones the engine itself documents.
EMBEDDING_PROVIDER_PARAM = "knowledge_base_embedding_provider"
EMBEDDING_MODEL_PARAM = "knowledge_base_embedding_model"
EMBEDDING_DIMENSIONS_PARAM = "knowledge_base_embedding_dimensions"
OPENAI_CREDENTIALS_NAME_PARAM = "knowledge_base_openai_credentials_name"


class KnowledgeBaseAppState(rx.State):
    """Shared, connection-free access to the knowledge-base stack.

    Holds no vars at all: it exists so the list state, the detail state and the add-document dialog
    resolve the embedding configuration in exactly one place, instead of each growing its own idea of
    which param names matter.

    Callers reach it with ``await self.get_state(KnowledgeBaseAppState)`` and then await one of its
    builders. **In a background event, both calls must happen inside the ``async with self:`` block**:
    a background handler's state is a proxy that refuses ``get_state`` outside its context manager
    (``ImmutableStateError``), and that is also why the main state is passed in as an argument rather
    than fetched here. Building the engine inside the lock is fine — it is a directory read; the long
    part (embedding, writing chunks) happens afterwards, outside it.
    """

    async def get_embedding_config(self, main_state: ReflexMainState) -> EmbeddingConfig:
        """The instance-level embedding configuration, resolved from the app params.

        The API key is resolved here rather than left to the engine because
        :func:`resolve_openai_api_key` raises a message worth showing a user (missing credentials,
        wrong credentials type) — and because a ``mock`` provider must not require a key at all,
        which is what makes an offline dev app possible.

        :param main_state: the app's main state, passed in rather than fetched with ``get_state`` so
                           this is callable from a background event (see the class docstring)
        :raises ValueError: if the named credentials do not exist or hold no API key
        """
        params = await main_state.get_params()

        provider = EmbeddingProvider(
            params.get(EMBEDDING_PROVIDER_PARAM) or EmbeddingProvider.OPENAI.value
        )
        if provider == EmbeddingProvider.MOCK:
            # The offline, deterministic configuration. Its dimensions are part of its identity, so
            # they come from the config class rather than from a param.
            return EmbeddingConfig.mock()

        return EmbeddingConfig(
            provider=provider,
            model=params.get(EMBEDDING_MODEL_PARAM) or DEFAULT_OPENAI_EMBEDDING_MODEL,
            api_key=resolve_openai_api_key(params.get(OPENAI_CREDENTIALS_NAME_PARAM)),
            dimensions=int(
                params.get(EMBEDDING_DIMENSIONS_PARAM) or DEFAULT_OPENAI_EMBEDDING_DIMENSIONS
            ),
        )

    async def build_engine(
        self, instance_scope: str, main_state: ReflexMainState
    ) -> KnowledgeBaseEngine:
        """A fresh engine for one instance scope, to be used and dropped within one operation.

        Never store the result on a state, in a class attribute or on a conversation object: it
        carries a LanceDB connection and takes a file lock on every call. Build it, use it, let it go
        out of scope.

        :param instance_scope: ``KnowledgeBase.instance_scope`` of the knowledge base being operated
                               on — the scope decides which vector space is opened, so passing the
                               wrong one silently addresses another instance
        :param main_state: the app's main state, for the same reason as in
                           :meth:`get_embedding_config`
        :raises ValueError: if the embedding configuration cannot be resolved
        :raises EmbeddingManifestMismatchError: on first use, if the instance was indexed with
                another embedding
        """
        embedding_config = await self.get_embedding_config(main_state)
        return KnowledgeBaseService.build_engine(
            instance_scope=instance_scope, embedding_config=embedding_config
        )
