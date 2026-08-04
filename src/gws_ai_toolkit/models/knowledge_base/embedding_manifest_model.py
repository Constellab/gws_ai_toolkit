"""The embedding manifest, held in the database rather than beside the vectors.

The engine's own default keeps its manifest in a JSON file inside the instance directory, which
makes it standalone. Once there is a database, the manifest belongs in it: it is administrative state
about a deployment, and it is what a future admin screen reads.

It is **keyed by instance scope from day one**. A single-row manifest table becomes silently wrong
the moment a second instance exists, and "silently" is the whole problem the manifest exists to
solve.

Known limitation, and the reason "no row" means *adopt* rather than *refuse*: the vectors live on
disk while this invariant lives in MariaDB, so a LanceDB directory copied or restored on its own
arrives with no row. A directory restored against a *different* database is still caught, as a
mismatch.
"""

from gws_core import Model
from peewee import CharField, IntegerField

from gws_ai_toolkit.core.ai_toolkit_db_manager import AiToolkitDbManager
from gws_ai_toolkit.rag.knowledge_base.embedding_manifest import (
    EmbeddingManifest,
    EmbeddingManifestStore,
)


class EmbeddingManifestModel(Model):
    """What one engine instance's vectors were produced with."""

    instance_scope: str = CharField(max_length=50, unique=True)
    provider: str = CharField(max_length=50)
    # Named ``embedding_model`` rather than ``model``: on a Peewee model class that name collides
    # with the framework's own vocabulary, and the column is internal to this table anyway.
    embedding_model: str = CharField(max_length=100)
    dimensions: int = IntegerField()

    class Meta:
        table_name = "gws_ai_toolkit_embedding_manifest"
        database = AiToolkitDbManager.get_instance().db
        is_table = True
        db_manager = AiToolkitDbManager.get_instance()

    def to_manifest(self) -> EmbeddingManifest:
        """Convert to the DTO the engine compares against its configuration."""
        return EmbeddingManifest(
            provider=self.provider,
            model=self.embedding_model,
            dimensions=self.dimensions,
        )


class DbEmbeddingManifestStore(EmbeddingManifestStore):
    """Keeps every instance's manifest in :class:`EmbeddingManifestModel`."""

    def get_manifest(self, instance_scope: str) -> EmbeddingManifest | None:
        """The manifest recorded for this instance scope, or None if there is none."""
        row = EmbeddingManifestModel.get_or_none(
            EmbeddingManifestModel.instance_scope == instance_scope
        )
        return row.to_manifest() if row else None

    @AiToolkitDbManager.transaction()
    def save_manifest(self, instance_scope: str, manifest: EmbeddingManifest) -> None:
        """Record the manifest for this instance scope, replacing any earlier row."""
        row = EmbeddingManifestModel.get_or_none(
            EmbeddingManifestModel.instance_scope == instance_scope
        )
        if row is None:
            row = EmbeddingManifestModel()
            row.instance_scope = instance_scope

        row.provider = manifest.provider
        row.embedding_model = manifest.model
        row.dimensions = manifest.dimensions
        row.save()
