import json
from datetime import datetime
from typing import List, Optional, cast

from gws_core import (CurrentUserService, DataHubS3ServerService, DateHelper,
                      EntityTag, EntityTagList, File, FileHelper,
                      ResourceModel, ResourceSearchBuilder, ResourceService,
                      RichText, RichTextAggregateDTO, Settings, SpaceFolder,
                      Tag, TagEntityType, TagOrigins, TagOriginType)


class DatahubRagFlowResource:
    """
    DatahubRagFlowResource is a class that wraps the resource object to manage
    the link between the datahub and the RagFlow app.
    """

    resource_model: ResourceModel

    _entity_tag_list: EntityTagList = None
    _tmp_dir: str = None

    # Tag key on resource to identify that it is sent to RagFlow
    # Value is the RagFlow document id
    RAGFLOW_DOC_TAG_KEY = 'ragflow_document'
    # Tag key on resource to identify that it is sent to RagFlow
    # Value is the RagFlow dataset id
    RAGFLOW_DATASET_TAG_KEY = 'ragflow_dataset'
    # Tag key on resource to identify that it is sent to RagFlow
    # Value ISO date time of the last sync with RagFlow
    RAGFLOW_SYNC_TAG_KEY = 'ragflow_sync'

    SUPPORTED_FILE_EXTENSIONS = ['txt', 'pdf', 'docx', 'doc', 'pptx', 'ppt',
                                'md', 'html', 'htm', 'xlsx', 'xls', 'csv', 'json']

    MAX_FILE_SIZE_MB = 50

    def __init__(self, resource_model: ResourceModel):
        self.resource_model = resource_model

    def is_compatible_with_ragflow(self) -> bool:
        """Check if the resource is compatible with RagFlow."""
        # Check if the resource is a file
        resource = self.resource_model.get_resource()
        if not isinstance(resource, File):
            return False

        if resource.extension not in self.SUPPORTED_FILE_EXTENSIONS:
            return False

        # If the file is a json, we only accept rich text json
        if resource.extension == 'json':
            try:
                dict_ = json.loads(resource.read())
                if not RichText.is_rich_text_json(dict_) and not RichTextAggregateDTO.json_is_rich_text_aggregate(dict_):
                    return False
            except json.JSONDecodeError as e:
                raise Exception(f"Error decoding JSON: {e}") from e

        # Check if the file size is less than 50 MB
        if resource.get_size() > self.MAX_FILE_SIZE_MB * 1024 * 1024:
            return False

        return True

    def get_ragflow_document_id(self) -> str | None:
        """Get the RagFlow document id from the resource tags."""
        resource_tags = self._get_tags()
        if not resource_tags.has_tag_key(self.RAGFLOW_DOC_TAG_KEY):
            return None

        tags = resource_tags.get_tags_by_key(self.RAGFLOW_DOC_TAG_KEY)
        return tags[0].tag_value

    def get_and_check_ragflow_document_id(self) -> str:
        """Get the RagFlow document id from the resource tags."""
        ragflow_document_id = self.get_ragflow_document_id()
        if ragflow_document_id is None:
            raise ValueError("The resource is not sent to RagFlow.")
        return ragflow_document_id

    def is_synced_with_ragflow(self) -> bool:
        """Check if the resource is synced with RagFlow."""
        resource_tags = self._get_tags()
        return resource_tags.has_tag_key(self.RAGFLOW_DOC_TAG_KEY)

    def get_ragflow_sync_date(self) -> datetime | None:
        """Get the RagFlow sync date from the resource tags."""
        resource_tags = self._get_tags()
        if not resource_tags.has_tag_key(self.RAGFLOW_SYNC_TAG_KEY):
            return None

        tags = resource_tags.get_tags_by_key(self.RAGFLOW_SYNC_TAG_KEY)
        return DateHelper.from_utc_milliseconds(int(tags[0].tag_value))

    def get_and_check_ragflow_sync_date(self) -> datetime:
        """Get the RagFlow sync date from the resource tags and check if it is not None."""
        ragflow_sync_date = self.get_ragflow_sync_date()
        if ragflow_sync_date is None:
            raise ValueError("The resource is not sent to RagFlow.")
        return ragflow_sync_date

    def get_ragflow_dataset_id(self) -> str:
        """Get the RagFlow dataset id from the resource tags."""
        resource_tags = self._get_tags()
        if not resource_tags.has_tag_key(self.RAGFLOW_DATASET_TAG_KEY):
            raise ValueError("The resource was not sent to RagFlow.")

        tags = resource_tags.get_tags_by_key(self.RAGFLOW_DATASET_TAG_KEY)
        return tags[0].tag_value

    def get_file_path(self) -> File:
        """Get the file path of the resource."""
        if not self.is_compatible_with_ragflow():
            raise ValueError("The resource is not compatible with RagFlow.")

        # For rich text, we convert it to a markdown file
        file = self._check_and_check_file()
        if file.extension == 'json':
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
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(rich_text.to_markdown())

            return File(file_path)

        return cast(File, self.resource_model.get_resource())

    def get_chunk_method(self, file_path: str) -> str:
        """Get the chunk method for the resource based on file extension."""
        extension = FileHelper.get_extension(file_path)

        # Map file extensions to appropriate RagFlow chunk methods
        if extension in ['pdf']:
            return 'paper'
        elif extension in ['docx', 'doc']:
            return 'book'
        elif extension in ['md']:
            return 'manual'
        elif extension in ['pptx', 'ppt']:
            return 'manual'
        elif extension in ['xlsx', 'xls', 'csv']:
            return 'table'
        else:
            return 'naive'  # Default method

    def get_parser_method(self, file_path: str) -> str:
        """Get the parser method for the resource based on file extension."""
        extension = FileHelper.get_extension(file_path)

        # Map file extensions to appropriate RagFlow parser methods
        if extension in ['pdf']:
            return 'paper'
        elif extension in ['docx', 'doc']:
            return 'book'
        elif extension in ['md', 'html', 'htm']:
            return 'manual'
        elif extension in ['pptx', 'ppt']:
            return 'manual'
        elif extension in ['xlsx', 'xls', 'csv']:
            return 'table'
        else:
            return 'naive'  # Default method

    def mark_resource_as_sent_to_ragflow(self, ragflow_document_id: str, ragflow_dataset_id: str) -> None:
        """Add tags to the resource."""
        resource_tags = self._get_tags()
        # Add the RagFlow document tag to the resource
        origins = TagOrigins(TagOriginType.USER, CurrentUserService.get_and_check_current_user().id)
        tags = [Tag(DatahubRagFlowResource.RAGFLOW_DOC_TAG_KEY, ragflow_document_id, origins=origins),
                Tag(DatahubRagFlowResource.RAGFLOW_DATASET_TAG_KEY, ragflow_dataset_id, origins=origins),
                Tag(DatahubRagFlowResource.RAGFLOW_SYNC_TAG_KEY, str(DateHelper.now_utc_as_milliseconds()), origins=origins)]
        resource_tags.replace_tags(tags)

    def unmark_resource_as_sent_to_ragflow(self) -> None:
        """Remove the RagFlow tags from the resource."""
        resource_tags = self._get_tags()
        entity_tags: List[EntityTag] = []
        entity_tags.extend(resource_tags.get_tags_by_key(self.RAGFLOW_DOC_TAG_KEY))
        entity_tags.extend(resource_tags.get_tags_by_key(self.RAGFLOW_DATASET_TAG_KEY))
        entity_tags.extend(resource_tags.get_tags_by_key(self.RAGFLOW_SYNC_TAG_KEY))

        tags = [tag.to_simple_tag() for tag in entity_tags]

        resource_tags.delete_tags(tags)

    def is_up_to_date_in_ragflow(self) -> bool:
        """Check if the resource is up to date in RagFlow."""
        ragflow_sync_date = self.get_ragflow_sync_date()
        if ragflow_sync_date is None:
            return False
        return ragflow_sync_date >= self.resource_model.last_modified_at

    def _get_tags(self) -> EntityTagList:
        """Get the tags of the resource."""
        if self._entity_tag_list is None:
            self._entity_tag_list = EntityTagList.find_by_entity(TagEntityType.RESOURCE, self.resource_model.id)
        return self._entity_tag_list

    def _check_and_check_file(self) -> File:
        """Check if the resource is a file and return it."""
        resource = self.resource_model.get_resource()
        if not isinstance(resource, File):
            raise ValueError("The resource is not a file.")
        return resource

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
        tags = self._get_tags()
        if not tags.has_tag_key(DataHubS3ServerService.KEY_TAG_NAME):
            raise ValueError("Could not find the datahub key.")
        return tags.get_tags_by_key(DataHubS3ServerService.KEY_TAG_NAME)[0].tag_value

    @staticmethod
    def from_resource_model_id(resource_model_id: str) -> 'DatahubRagFlowResource':
        """Create a DatahubRagFlowResource from a resource model id."""
        resource_model = ResourceService.get_by_id_and_check(resource_model_id)
        return DatahubRagFlowResource(resource_model)

    @staticmethod
    def from_ragflow_document_id(ragflow_document_id: str) -> Optional['DatahubRagFlowResource']:
        """Create a DatahubRagFlowResource from a RagFlow document id."""
        # retrieve all the files stored in the datahub
        research_search = ResourceSearchBuilder()
        research_search.add_tag_filter(Tag(DatahubRagFlowResource.RAGFLOW_DOC_TAG_KEY, ragflow_document_id))
        resource_model = research_search.search_first()

        if not resource_model:
            return None

        return DatahubRagFlowResource(resource_model)