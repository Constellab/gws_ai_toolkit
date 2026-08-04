"""Disk layout of the embedded knowledge-base stack.

```
<brick_extension_dir>/gws_ai_toolkit/knowledge_base/
├── instances/<scope>/lancedb/          vector + full-text indexes for that instance
├── instances/<scope>/.lock             flock target
├── instances/<scope>/embedding_manifest.json
└── files/<knowledge_base_id>/<document_id>_<sanitised_filename>    snapshots
```

An *instance* is one LanceDB directory holding the chunks of every knowledge base in its scope.
Scoping is structural, not a filter: a second scope is a second directory, a second manifest and a
second lock, sharing no rows with the first. V1 ships the ``default`` scope; a per-lab or a
community deployment is another scope and needs no engine change.

``BrickService.get_brick_extension_dir`` takes ``(brick_name, extension_name)`` and joins them, so
sub-directories are joined onto the directory it returns rather than passed as a nested name.
"""

import os
import re

from gws_core import BrickService

BRICK_NAME = "gws_ai_toolkit"
EXTENSION_NAME = "knowledge_base"
DEFAULT_INSTANCE_SCOPE = "default"

INSTANCES_DIR_NAME = "instances"
FILES_DIR_NAME = "files"
LANCEDB_DIR_NAME = "lancedb"
LOCK_FILE_NAME = ".lock"

# Anything outside this set is replaced in a snapshot file name: the name reaches us from user
# input (an upload, a resource name) and ends up as a path segment.
_UNSAFE_FILENAME_CHARS = re.compile(r"[^A-Za-z0-9._-]+")
_MAX_SANITISED_FILENAME_LENGTH = 100


class KnowledgeBaseStorage:
    """Resolves every path the knowledge-base stack writes to."""

    @classmethod
    def get_base_dir(cls) -> str:
        """Root directory of the knowledge-base data, created if missing."""
        base_dir = BrickService.get_brick_extension_dir(BRICK_NAME, EXTENSION_NAME)
        os.makedirs(base_dir, exist_ok=True)
        return base_dir

    @classmethod
    def get_instance_dir(cls, instance_scope: str = DEFAULT_INSTANCE_SCOPE) -> str:
        """Directory of one engine instance, created if missing."""
        instance_dir = os.path.join(cls.get_base_dir(), INSTANCES_DIR_NAME, instance_scope)
        os.makedirs(instance_dir, exist_ok=True)
        return instance_dir

    @classmethod
    def get_lancedb_dir(cls, instance_dir: str) -> str:
        """LanceDB directory of an instance (LanceDB creates it on first write)."""
        return os.path.join(instance_dir, LANCEDB_DIR_NAME)

    @classmethod
    def get_lock_file_path(cls, instance_dir: str) -> str:
        """flock target guarding every access to an instance."""
        return os.path.join(instance_dir, LOCK_FILE_NAME)

    @classmethod
    def get_files_dir(cls, knowledge_base_id: str) -> str:
        """Snapshot directory of a knowledge base, created if missing."""
        files_dir = os.path.join(cls.get_base_dir(), FILES_DIR_NAME, knowledge_base_id)
        os.makedirs(files_dir, exist_ok=True)
        return files_dir

    @classmethod
    def get_snapshot_path(cls, knowledge_base_id: str, document_id: str, filename: str) -> str:
        """Path of a document's snapshot — the only copy indexing ever reads."""
        return os.path.join(
            cls.get_files_dir(knowledge_base_id),
            f"{document_id}_{cls.sanitise_filename(filename)}",
        )

    @staticmethod
    def sanitise_filename(filename: str) -> str:
        """Make a user-provided file name safe to use as a path segment."""
        name = _UNSAFE_FILENAME_CHARS.sub("_", os.path.basename(filename)).strip("._")
        if not name:
            name = "document"
        return name[:_MAX_SANITISED_FILENAME_LENGTH]
