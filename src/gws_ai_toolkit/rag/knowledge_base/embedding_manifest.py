"""The embedding manifest — the guard that keeps one instance in one vector space.

Several knowledge bases share one LanceDB instance, separated only by a metadata filter, so they
must share one embedding. Changing the model or the dimensions of a populated instance fails in
the dangerous direction: a width change errors loudly, but ``text-embedding-3-large`` truncated to
1536 dimensions — or a ``mock`` ↔ ``openai`` swap — has the *same width in a different space*. No
error, plausible-looking scores, near-random chunks.

So the engine records what it indexed with, and refuses to read **or** write an instance whose
record disagrees with the configuration it was handed. Re-indexing after an intentional model
change becomes an explicit, logged operation instead of a silent corruption.

The store is an interface on purpose. The default keeps the manifest next to the vectors, which
makes the engine standalone and makes a copied directory carry its own invariant. The persistence
layer replaces it with a database-backed store keyed by instance scope.
"""

import json
import os
from abc import ABC, abstractmethod

from gws_core import BaseModelDTO, Logger

from .knowledge_base_config import EmbeddingConfig

MANIFEST_FILE_NAME = "embedding_manifest.json"


class EmbeddingManifest(BaseModelDTO):
    """What an instance's vectors were produced with."""

    provider: str
    model: str
    dimensions: int

    @classmethod
    def from_config(cls, config: EmbeddingConfig) -> "EmbeddingManifest":
        return cls(
            provider=str(config.provider.value),
            model=config.model,
            dimensions=config.dimensions,
        )

    def describe(self) -> str:
        return f"provider={self.provider}, model={self.model}, dimensions={self.dimensions}"


class EmbeddingManifestMismatchError(Exception):
    """Raised when an instance was indexed with a different embedding than the one configured."""


class EmbeddingManifestStore(ABC):
    """Where the manifest of an instance is kept."""

    @abstractmethod
    def get_manifest(self, instance_scope: str) -> EmbeddingManifest | None:
        """Return the manifest recorded for this instance scope, or None if there is none."""

    @abstractmethod
    def save_manifest(self, instance_scope: str, manifest: EmbeddingManifest) -> None:
        """Record the manifest for this instance scope."""


class FileEmbeddingManifestStore(EmbeddingManifestStore):
    """Default store: one JSON file inside the instance directory.

    Keeping it beside the vectors means a directory that is copied or restored carries its own
    invariant, and that the engine needs no database.
    """

    def __init__(self, instance_dir: str) -> None:
        self._file_path = os.path.join(instance_dir, MANIFEST_FILE_NAME)

    def get_manifest(self, instance_scope: str) -> EmbeddingManifest | None:
        if not os.path.exists(self._file_path):
            return None
        with open(self._file_path, encoding="utf-8") as file:
            return EmbeddingManifest.from_json(json.load(file))

    def save_manifest(self, instance_scope: str, manifest: EmbeddingManifest) -> None:
        os.makedirs(os.path.dirname(self._file_path), exist_ok=True)
        # Write then rename, so a crash mid-write cannot leave a half-written manifest that would
        # read as a mismatch on the next open.
        temp_path = f"{self._file_path}.tmp"
        with open(temp_path, "w", encoding="utf-8") as file:
            json.dump(manifest.to_json_dict(), file, indent=2)
        os.replace(temp_path, self._file_path)


def validate_or_adopt_manifest(
    store: EmbeddingManifestStore, instance_scope: str, config: EmbeddingConfig
) -> None:
    """Fail closed on a manifest mismatch, adopt the configuration when there is no manifest.

    :param store: where the manifest is kept
    :param instance_scope: the instance this manifest belongs to
    :param config: the embedding configuration the engine was opened with
    :raises EmbeddingManifestMismatchError: if a manifest exists and disagrees with ``config``
    """
    expected = EmbeddingManifest.from_config(config)
    recorded = store.get_manifest(instance_scope)

    if recorded is None:
        # First run, or a directory adopted from elsewhere: record what we are about to index with.
        store.save_manifest(instance_scope, expected)
        Logger.info(
            f"Knowledge base instance '{instance_scope}' adopted the embedding "
            f"configuration: {expected.describe()}"
        )
        return

    if recorded != expected:
        raise EmbeddingManifestMismatchError(
            f"Knowledge base instance '{instance_scope}' was indexed with a different embedding. "
            f"Recorded: {recorded.describe()}. Configured: {expected.describe()}. "
            "Reading or writing it with this configuration would return near-random chunks. "
            "Restore the recorded embedding configuration, or re-index the instance from scratch."
        )
