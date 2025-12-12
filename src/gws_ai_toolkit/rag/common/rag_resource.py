import json
from datetime import datetime
from typing import Optional, cast

from gws_core import (
    CurrentUserService,
    DataHubS3ServerService,
    DateHelper,
    EntityTag,
    EntityTagList,
    File,
    FileHelper,
    ResourceModel,
    ResourceSearchBuilder,
    ResourceService,
    RichText,
    RichTextAggregateDTO,
    Settings,
    SpaceFolder,
    Tag,
    TagEntityType,
    TagOrigins,
    TagOriginType,
)

from .rag_enums import RAG_COMMON_MAX_FILE_SIZE_MB, RAG_COMMON_SUPPORTED_EXTENSIONS


class RagResource:
    """
    Resource wrappers that manage links
    between the data lab and RAG platforms.
    """

    resource_model: ResourceModel
    _entity_tag_list: EntityTagList = None
    _tmp_dir: str = None

    # Common constants
    SUPPORTED_FILE_EXTENSIONS = RAG_COMMON_SUPPORTED_EXTENSIONS
    MAX_FILE_SIZE_MB = RAG_COMMON_MAX_FILE_SIZE_MB

    # Tag keys specific to RagFlow
    RAG_DOC_TAG_KEY = "rag_document"
    RAG_DATASET_ID_TAG_KEY = "rag_dataset_id"
    RAG_SYNC_TAG_KEY = "rag_sync"

    def __init__(self, resource_model: ResourceModel):
        self.resource_model = resource_model

    # Common methods
    def is_compatible_with_rag(self) -> bool:
        """Check if the resource is compatible with the RAG platform."""
        resource = self.resource_model.get_resource()
        if not isinstance(resource, File):
            return False

        if resource.extension not in self.SUPPORTED_FILE_EXTENSIONS:
            return False

        # If the file is a json, we only accept rich text json
        if resource.extension == "json":
            try:
                dict_ = json.loads(resource.read())
                if not RichText.is_rich_text_json(
                    dict_
                ) and not RichTextAggregateDTO.json_is_rich_text_aggregate(dict_):
                    return False
            except json.JSONDecodeError as e:
                raise Exception(f"Error decoding JSON: {e}") from e

        # Check file size
        if resource.get_size() > self.MAX_FILE_SIZE_MB * 1024 * 1024:
            return False

        return True

    def get_document_id(self) -> str | None:
        """Get the document id from the resource tags."""
        resource_tags = self.get_tags()
        if not resource_tags.has_tag_key(self.RAG_DOC_TAG_KEY):
            return None

        tags = resource_tags.get_tags_by_key(self.RAG_DOC_TAG_KEY)
        return tags[0].tag_value

    def get_and_check_document_id(self) -> str:
        """Get the document id from the resource tags and check if it exists."""
        document_id = self.get_document_id()
        if document_id is None:
            raise ValueError("The resource is not sent to RAG.")
        return document_id

    def is_synced_with_rag(self) -> bool:
        """Check if the resource is synced with the platform."""
        resource_tags = self.get_tags()
        return resource_tags.has_tag_key(self.RAG_DOC_TAG_KEY)

    def get_sync_date(self) -> datetime | None:
        """Get the sync date from the resource tags."""
        resource_tags = self.get_tags()
        if not resource_tags.has_tag_key(self.RAG_SYNC_TAG_KEY):
            return None

        tags = resource_tags.get_tags_by_key(self.RAG_SYNC_TAG_KEY)
        return DateHelper.from_utc_milliseconds(int(tags[0].tag_value))

    def get_and_check_sync_date(self) -> datetime:
        """Get the sync date from the resource tags and check if it exists."""
        sync_date = self.get_sync_date()
        if sync_date is None:
            raise ValueError("The resource is not sent to RAG.")
        return sync_date

    def get_dataset_base_id(self) -> str:
        """Get the dataset base id from the resource tags."""
        resource_tags = self.get_tags()
        if not resource_tags.has_tag_key(self.RAG_DATASET_ID_TAG_KEY):
            raise ValueError("The resource was not sent to RAG.")

        tags = resource_tags.get_tags_by_key(self.RAG_DATASET_ID_TAG_KEY)
        return tags[0].tag_value

    def get_file(self) -> File:
        """Get the file path of the resource."""
        if not self.is_compatible_with_rag():
            raise ValueError("The resource is not compatible with RAG.")

        # For rich text, we convert it to a markdown file
        file = self.get_raw_file()
        if file.extension == "json":
            rich_text: RichText = None
            dict_ = json.loads(file.read())

            if RichText.is_rich_text_json(dict_):
                rich_text = RichText.from_json(dict_)
            elif RichTextAggregateDTO.json_is_rich_text_aggregate(dict_):
                aggregate_dto = RichTextAggregateDTO.from_json(dict_)
                rich_text = RichText(aggregate_dto.richText)
            else:
                raise ValueError("The json resource is not a rich text.")

            self._tmp_dir = Settings.make_temp_dir()
            file_path = f"{self._tmp_dir}/{file.name}.md"
            with open(file_path, "w", encoding="utf-8") as f:
                f.write(rich_text.to_markdown())

            return File(file_path)

        return cast(File, self.resource_model.get_resource())

    def mark_resource_as_sent_to_rag(self, document_id: str, dataset_id: str) -> None:
        """Add tags to the resource."""
        resource_tags = self.get_tags()
        origins = TagOrigins(TagOriginType.USER, CurrentUserService.get_and_check_current_user().id)
        tags = [
            Tag(self.RAG_DOC_TAG_KEY, document_id, origins=origins),
            Tag(self.RAG_DATASET_ID_TAG_KEY, dataset_id, origins=origins),
            Tag(self.RAG_SYNC_TAG_KEY, str(DateHelper.now_utc_as_milliseconds()), origins=origins),
        ]
        resource_tags.replace_tags(tags)

    def unmark_resource_as_sent_to_rag(self) -> None:
        """Remove the platform tags from the resource."""
        resource_tags = self.get_tags()
        entity_tags: list[EntityTag] = []
        entity_tags.extend(resource_tags.get_tags_by_key(self.RAG_DOC_TAG_KEY))
        entity_tags.extend(resource_tags.get_tags_by_key(self.RAG_DATASET_ID_TAG_KEY))
        entity_tags.extend(resource_tags.get_tags_by_key(self.RAG_SYNC_TAG_KEY))

        tags = [tag.to_simple_tag() for tag in entity_tags]
        resource_tags.delete_tags(tags)

    def is_up_to_date_in_rag(self) -> bool:
        """Check if the resource is up to date in the platform."""
        sync_date = self.get_sync_date()
        if sync_date is None:
            return False
        return sync_date >= self.resource_model.last_modified_at

    def get_root_folder(self) -> SpaceFolder | None:
        """Get the root folder of the resource."""
        if not self.resource_model.folder:
            return None
        return self.resource_model.folder.get_root()

    def clear_tmp_dir(self) -> None:
        """Clear the tmp dir."""
        if self._tmp_dir is not None:
            FileHelper.delete_dir(self._tmp_dir)
            self._tmp_dir = None

    def get_datahub_key(self) -> str:
        """Get the datahub key of the resource."""
        tags = self.get_tags()
        if not tags.has_tag_key(DataHubS3ServerService.KEY_TAG_NAME):
            raise ValueError("Could not find the datahub key.")
        return tags.get_tags_by_key(DataHubS3ServerService.KEY_TAG_NAME)[0].tag_value

    # Private helper methods
    def get_tags(self) -> EntityTagList:
        """Get the tags of the resource."""
        if self._entity_tag_list is None:
            self._entity_tag_list = EntityTagList.find_by_entity(
                TagEntityType.RESOURCE, self.resource_model.id
            )
        return self._entity_tag_list

    def get_raw_file(self) -> File:
        """Check if the resource is a file and return it."""
        resource = self.resource_model.get_resource()
        if not isinstance(resource, File):
            raise ValueError("The resource is not a file.")
        return resource

    @classmethod
    def get_chunk_separator(cls, file_path: str) -> str:
        """Get the chunk separator for the resource."""
        extension = FileHelper.get_normalized_extension(file_path)
        # for markdown
        if extension == "md":
            return "## "
        return "\n\n"

    def get_id(self) -> str:
        """Get the ID of the resource."""
        return self.resource_model.id

    # Static factory methods

    @classmethod
    def from_resource_model_id(cls, resource_model_id: str):
        """Create a resource wrapper from a resource model id."""
        resource_model = ResourceService.get_by_id_and_check(resource_model_id)
        return cls(resource_model)

    @classmethod
    def from_document_id(cls, document_id: str) -> Optional["RagResource"]:
        """Create a resource wrapper from a platform document id."""
        research_search = ResourceSearchBuilder()
        research_search.add_tag_filter(Tag(cls.RAG_DOC_TAG_KEY, document_id))
        resource_model = research_search.search_first()

        if not resource_model:
            return None

        return cls(resource_model)

    @classmethod
    def from_document_or_resource_id_and_check(cls, id_: str) -> "RagResource":
        """Create a resource wrapper from either a document id or a resource model id."""
        rag_resource = cls.from_document_id(id_)
        if rag_resource:
            return rag_resource

        return cls.from_resource_model_id(id_)
