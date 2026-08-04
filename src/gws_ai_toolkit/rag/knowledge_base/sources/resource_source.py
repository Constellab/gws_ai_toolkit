"""The built-in ``resource`` document source: files stored as lab resources.

This is the **one file in the knowledge-base layer that imports ``RagResource``**, and it is on
purpose: everything the rest of the stack knows about a document is ``source_type`` + ``source_id``,
so all the lab-specific knowledge — what counts as a fetchable resource, how a note becomes
Markdown, how a resource is opened, how tagged resources are enumerated — is concentrated here.
Delete this file and the knowledge base still works; it simply has no lab resources in it.

Three decisions worth stating.

**Rich text becomes Markdown at fetch time, not at index time.** The loader can read a rich-text
``.json`` on its own, so this conversion is not what makes indexing work — it is what makes the
*snapshot* readable. A snapshot is what AI Expert reads, what a user downloads and what survives the
resource being deleted, and none of those are helped by a wall of editor JSON. The version marker is
then the hash of the **converted** bytes, so it changes when the note's text changes and not when its
editor metadata does.

**The admission checks run twice, cheaply first.** ``KnowledgeBaseService`` is what decides whether a
fetched file may be indexed, and it is the authority. But it can only decide once the file has been
copied, and copying a 400 MB resource to reject it for size is pointless work — so the extension and
the size are pre-checked here, against the same rules, before anything is copied. A rich-text
resource is measured on its stored JSON, which is the rule ``RagResource`` has always applied.

**The tag search is one-shot, not a subscription.** ``list_documents`` is the search salvaged from
``TagRagAppService.get_all_resources_to_send_to_rag`` — tag filter, fs-node, not archived. Nothing
here is written back to the resource: no ``rag_document``, no ``rag_dataset_id``, no ``rag_sync``
tag. Membership lives in ``KnowledgeBaseDocument`` rows, and an import only ever adds.
"""

import os
import tempfile

from gws_core import (
    File,
    FileHelper,
    Logger,
    ResourceModel,
    ResourceSearchBuilder,
    Settings,
    Tag,
)

from gws_ai_toolkit.core.utils import Utils
from gws_ai_toolkit.models.knowledge_base.knowledge_base_dto import KnowledgeBaseDocumentDTO
from gws_ai_toolkit.rag.common.rag_resource import RagResource
from gws_ai_toolkit.rag.knowledge_base.document_compatibility import DocumentCompatibility
from gws_ai_toolkit.rag.knowledge_base.document_loader import (
    RICH_TEXT_EXTENSIONS,
    DocumentLoader,
)

from .knowledge_base_source import (
    DocumentSourceOperationNotSupportedError,
    KnowledgeBaseDocumentSource,
    SourceDocumentCandidate,
    SourceFetchResult,
    SourceOpenAction,
    compute_bytes_content_hash,
    compute_file_content_hash,
)

RESOURCE_SOURCE_TYPE = "resource"

# The keys of the import criterion this provider understands. They are also the shape stamped into
# ``source_metadata["imported_from"]`` by the service, which is what lets a later reconciliation tell
# an imported document from a hand-picked one.
TAG_KEY_CRITERION = "tag_key"
TAG_VALUE_CRITERION = "tag_value"

# Prefix of the temporary copies handed to the service, so a leftover file is identifiable.
FETCH_TEMP_FILE_PREFIX = "kb_resource_fetch_"


class ResourceDocumentSource(KnowledgeBaseDocumentSource):
    """Lab resources as knowledge-base documents, addressed by their resource-model id."""

    source_type = RESOURCE_SOURCE_TYPE

    ############################################### FETCH ###############################################

    def fetch_file(self, source_id: str | None, source_metadata: dict | None) -> SourceFetchResult:
        """Copy a lab resource's file to a temporary path, converting rich text to Markdown.

        :param source_id: id of the resource model behind the document
        :param source_metadata: unused by this provider — the resource id is the whole address
        :raises DocumentSourceOperationNotSupportedError: if the resource is gone, is not a file, or
                its file is no longer in the file store
        :raises UnsupportedDocumentFormatError: if the format cannot be indexed
        :raises DocumentTooLargeError: if the resource is above the size cap
        """
        file = self._get_file_and_check(source_id)
        filename = self._get_filename(file)
        extension = DocumentLoader.get_extension(filename)

        # Cheap rejections first, before a byte is copied.
        DocumentLoader.check_extension_is_supported(extension)
        DocumentCompatibility.check_size_is_within_cap(file.get_size(), filename)

        if extension in RICH_TEXT_EXTENSIONS:
            content = DocumentLoader.read_rich_text(file.path).to_markdown().encode("utf-8")
            temp_path = self._make_temp_path(".md")
            with open(temp_path, "wb") as temp_file:
                temp_file.write(content)
            return SourceFetchResult(
                path=temp_path,
                filename=f"{os.path.splitext(filename)[0]}.md",
                version_marker=compute_bytes_content_hash(content),
            )

        # A copy, never the resource's own path: the service deletes the fetched file once it has
        # been snapshotted, and that would delete the lab resource's content.
        temp_path = self._make_temp_path(extension)
        FileHelper.copy_file(file.path, temp_path)
        return SourceFetchResult(
            path=temp_path,
            filename=filename,
            version_marker=compute_file_content_hash(temp_path),
        )

    def get_version_marker(self, source_id: str | None, source_metadata: dict | None) -> str | None:
        """Content hash of the resource as it stands now, or ``None`` if it cannot be read.

        Computed without copying anything, and by the same rules as :meth:`fetch_file` — the
        converted Markdown for a note, the file's own bytes otherwise — so the two markers are
        comparable. ``None`` covers every "cannot answer" case: a deleted resource, a resource that
        is not a file, a file missing from the store, note content that turned out to be data JSON.
        """
        file = self._get_file_or_none(source_id)
        if file is None:
            return None

        extension = DocumentLoader.get_extension(self._get_filename(file))
        try:
            if extension in RICH_TEXT_EXTENSIONS:
                markdown = DocumentLoader.read_rich_text(file.path).to_markdown()
                return compute_bytes_content_hash(markdown.encode("utf-8"))
            return compute_file_content_hash(file.path)
        except Exception as err:
            # Reporting "unknown" is the contract here; raising would turn a sync report into a
            # failure for a document whose snapshot is perfectly usable.
            Logger.warning(f"Cannot compute the version marker of resource '{source_id}': {err}")
            return None

    ############################################### OPEN ###############################################

    def get_open_action(self, document: KnowledgeBaseDocumentDTO) -> SourceOpenAction | None:
        """Open the live resource through a temporary share link.

        Falls back to the snapshot whenever the link cannot be produced — a deleted resource, a
        share service that refuses — because the snapshot is the copy that is always there.
        """
        if not document.source_id:
            return SourceOpenAction.download_snapshot()

        try:
            url = Utils.generate_temp_share_resource_link(document.source_id)
        except Exception as err:
            Logger.warning(
                f"Cannot share resource '{document.source_id}' behind knowledge-base document "
                f"'{document.id}', serving its snapshot instead: {err}"
            )
            return SourceOpenAction.download_snapshot()

        if not url:
            return SourceOpenAction.download_snapshot()
        return SourceOpenAction.external_link(url)

    ############################################### ENUMERATE ###############################################

    def list_documents(self, criteria: dict) -> list[SourceDocumentCandidate]:
        """Every non-archived file resource carrying the requested tag.

        The three filters are the ones ``TagRagAppService`` used, and they matter: without
        ``add_is_fs_node_filter`` the search returns tables and robots that no fetch could produce,
        and without the archived filter it returns resources a user has already put away.

        :param criteria: ``{"tag_key": ..., "tag_value": ...}``; an empty or missing ``tag_value``
                         matches every value of that key
        :raises ValueError: if no tag key is given — an import with no criterion would enumerate the
                whole lab
        """
        criteria = criteria or {}
        tag_key = str(criteria.get(TAG_KEY_CRITERION) or "").strip()
        tag_value = str(criteria.get(TAG_VALUE_CRITERION) or "").strip()
        if not tag_key:
            raise ValueError(
                "Importing lab resources needs a tag key: without one, every resource in the lab "
                "would be a candidate."
            )

        search = ResourceSearchBuilder()
        if tag_value:
            search.add_tag_filter(Tag(tag_key, tag_value))
        else:
            search.add_tag_key_filter(tag_key)
        search.add_is_fs_node_filter()
        search.add_is_archived_filter(False)

        return [
            SourceDocumentCandidate(
                source_id=resource_model.id,
                filename=resource_model.name or resource_model.id,
                # No version marker: computing one means reading the resource, and the service
                # hashes the copy it fetches anyway. A candidate is a name and an address.
            )
            for resource_model in search.search_all()
        ]

    ############################################### INTERNALS ###############################################

    @classmethod
    def _get_file_and_check(cls, source_id: str | None) -> File:
        """The resource's file, or a message saying why there is none.

        :raises DocumentSourceOperationNotSupportedError: if the resource cannot yield a file
        """
        if not source_id:
            raise DocumentSourceOperationNotSupportedError(
                "A resource-backed document needs the id of its lab resource."
            )

        resource_model = ResourceModel.get_by_id(source_id)
        if resource_model is None:
            raise DocumentSourceOperationNotSupportedError(
                f"Resource '{source_id}' no longer exists in the lab, so it cannot be fetched. Its "
                f"snapshot is still readable and still indexed."
            )

        try:
            file = RagResource(resource_model).get_raw_file()
        except ValueError as err:
            raise DocumentSourceOperationNotSupportedError(
                f"Resource '{resource_model.name or source_id}' is not a file, so it cannot be "
                f"indexed as a document."
            ) from err

        if not file.exists():
            raise DocumentSourceOperationNotSupportedError(
                f"The file of resource '{resource_model.name or source_id}' is no longer in the "
                f"lab's file store, so it cannot be fetched."
            )
        return file

    @classmethod
    def _get_file_or_none(cls, source_id: str | None) -> File | None:
        """The resource's file, or ``None`` — for the read paths that must not fail."""
        try:
            return cls._get_file_and_check(source_id)
        except DocumentSourceOperationNotSupportedError:
            return None

    @staticmethod
    def _get_filename(file: File) -> str:
        """The name to record for a resource's file, extension included.

        The resource's own name is preferred: it is what a user recognises in a source pill. It is
        normally stored with its extension, but a resource renamed by hand may have lost it, and the
        extension is what decides which reader runs — so the file's own is appended when it is
        missing.
        """
        filename = file.name or file.get_base_name()
        if DocumentLoader.get_extension(filename):
            return filename
        return f"{filename}{DocumentLoader.get_extension(file.path)}"

    @staticmethod
    def _make_temp_path(extension: str) -> str:
        """An empty temporary file the service may delete when it is done with it.

        A bare file rather than a file inside a temporary *directory*: the fetch contract lets the
        caller delete the file, not a directory around it, so a per-fetch directory would be left
        behind on every import — fifty resources, fifty empty directories.
        """
        root_temp_dir = Settings.get_instance().get_root_temp_dir()
        FileHelper.create_dir_if_not_exist(root_temp_dir)
        handle, path = tempfile.mkstemp(
            prefix=FETCH_TEMP_FILE_PREFIX, suffix=extension, dir=root_temp_dir
        )
        os.close(handle)
        return path


ResourceDocumentSource.register()
