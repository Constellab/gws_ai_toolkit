"""Service for common operations when downloading Community files."""

from gws_core import (
    EntityTagList,
    ResourceModel,
    ResourceOrigin,
    ResourceSearchBuilder,
    Scenario,
    Tag,
    TagEntityType,
    TagService,
    TaskModel,
)
from gws_core.tag.tag import TagOrigins

from ..rag.common.rag_resource import RagResource


class CommunityDownloadService:
    """Service providing common operations for downloading and managing Community files."""

    @staticmethod
    def ensure_tag_keys_exist(tag_keys: list[tuple[str, str]], logger=None) -> None:
        """
        Ensure that the required tag keys exist.
        Creates them if they don't exist.

        :param tag_keys: List of tuples (key, label) for tags to create.
        :param logger: Optional logger with log_info_message method.
        """
        for key, label in tag_keys:
            existing_key = TagService.get_by_key(key)
            if not existing_key:
                TagService.create_tag_key(key, label)
                if logger:
                    logger.log_info_message(f"Created tag key '{key}'")

    @staticmethod
    def find_existing_resource_by_tag(tag_key: str, tag_value: str) -> ResourceModel | None:
        """
        Find an existing resource with a specific tag.

        :param tag_key: Tag key to search for.
        :param tag_value: Tag value to search for.
        :return: ResourceModel if found, None otherwise.
        """
        search_builder = ResourceSearchBuilder()
        search_builder.add_tag_filter(Tag(tag_key, tag_value))
        search_builder.add_is_archived_filter(False)

        results = search_builder.search_all()

        if len(results) > 0:
            return results[0]

        return None

    @staticmethod
    def get_existing_brick_files(brick_name: str, send_to_rag_value: str) -> list[ResourceModel]:
        """
        Get all existing File resources for a specific brick.

        :param brick_name: Name of the brick.
        :param send_to_rag_value: Value for the send_to_rag tag (e.g., 'CommunityDocumentations').
        :return: List of ResourceModel instances.
        """
        search_builder = ResourceSearchBuilder()
        search_builder.add_tag_filter(Tag("send_to_rag", send_to_rag_value))
        search_builder.add_tag_filter(Tag("community_brick_name", brick_name))
        search_builder.add_is_archived_filter(False)

        return search_builder.search_all()

    @staticmethod
    def copy_rag_tags(entity_tags: EntityTagList) -> list[Tag]:
        """
        Copy RAG-related tags from an existing resource.

        :param entity_tags: EntityTagList of the existing resource.
        :return: List of Tag objects for RAG tags.
        """
        rag_tags = []

        rag_tag_keys = [
            RagResource.RAG_DOC_TAG_KEY,
            RagResource.RAG_DATASET_ID_TAG_KEY,
            RagResource.RAG_SYNC_TAG_KEY,
        ]

        for tag_key in rag_tag_keys:
            entity_tag = entity_tags.get_first_tag_by_key(tag_key)
            if entity_tag:
                rag_tags.append(entity_tag.to_simple_tag())

        return rag_tags

    @staticmethod
    def copy_rag_tags_from_resource_id(resource_id: str) -> list[Tag]:
        """
        Copy RAG-related tags from an existing resource by its ID.

        :param resource_id: ID of the resource to copy tags from.
        :return: List of RAG tags to copy.
        """
        entity_tags = EntityTagList.find_by_entity(TagEntityType.RESOURCE, resource_id)
        return CommunityDownloadService.copy_rag_tags(entity_tags)

    @staticmethod
    def should_update_resource(
        existing_resource: ResourceModel | None,
        new_last_modified_at: str | None,
        logger=None
    ) -> tuple[bool, list[Tag] | None]:
        """
        Check if a resource should be updated based on last_modified_at.

        :param existing_resource: Existing resource model.
        :param new_last_modified_at: New last modification date.
        :param logger: Optional logger with log_info_message method.
        :return: Tuple (should_download, rag_tags_to_copy).
        """
        if not existing_resource:
            return True, None

        # Get the existing last_modified_at tag
        existing_tags = EntityTagList.find_by_entity(TagEntityType.RESOURCE, existing_resource.id)
        existing_modified_tag = existing_tags.get_first_tag_by_key("community_last_modificated_at")

        if existing_modified_tag and new_last_modified_at:
            existing_date = existing_modified_tag.get_tag_value()
            if existing_date == new_last_modified_at:
                # No update needed
                return False, None
            else:
                # Changed, need to update
                rag_tags = CommunityDownloadService.copy_rag_tags(existing_tags)
                return True, rag_tags
        else:
            # No date info, update to be safe
            rag_tags = CommunityDownloadService.copy_rag_tags(existing_tags)
            return True, rag_tags

    @staticmethod
    def save_resource_with_context(
        resource,
        scenario: Scenario | None,
        task_model: TaskModel | None
    ) -> ResourceModel:
        """
        Save a resource with proper context (scenario and task model).

        :param resource: Resource to save.
        :param scenario: Scenario context.
        :param task_model: Task model context.
        :return: Saved ResourceModel.
        """
        if scenario and task_model:
            return ResourceModel.save_from_resource(
                resource=resource,
                origin=ResourceOrigin.GENERATED,
                scenario=scenario,
                task_model=task_model,
            )
        else:
            return ResourceModel.save_from_resource(
                resource=resource,
                origin=ResourceOrigin.UPLOADED,
            )

    @staticmethod
    def mark_resources_for_deletion(
        resource_ids: list[str],
        logger=None
    ) -> int:
        """
        Mark resources for deletion by adding the 'delete_in_next_sync' tag.

        :param resource_ids: List of resource IDs to mark.
        :param logger: Optional logger with log_warning_message and log_error_message methods.
        :return: Number of resources successfully marked.
        """
        deleted_count = 0
        for resource_id in resource_ids:
            try:
                resource = ResourceModel.get_by_id_and_check(resource_id)
                resource_name = resource.get_resource().name if resource else resource_id

                # Add 'delete_in_next_sync' tag
                entity_tags = EntityTagList.find_by_entity(TagEntityType.RESOURCE, resource_id)
                tag = Tag("delete_in_next_sync", "True", origins=TagOrigins.system_origins())
                entity_tags.add_tag(tag)

                deleted_count += 1
                if logger:
                    logger.log_warning_message(
                        f"Marked '{resource_name}' for deletion - no longer exists in Community"
                    )
            except Exception as e:
                if logger:
                    logger.log_error_message(f"Failed to mark resource {resource_id} for deletion: {str(e)}")

        return deleted_count

    @staticmethod
    def handle_no_documentation_case(
        existing_resources: list[ResourceModel],
        brick_name: str,
        doc_type: str,
        logger=None
    ) -> None:
        """
        Handle the case where no documentation is found in Community.
        Marks all existing resources for deletion.

        :param existing_resources: List of existing resources.
        :param brick_name: Name of the brick.
        :param doc_type: Type of documentation (for logging).
        :param logger: Optional logger.
        """
        if logger:
            logger.log_warning_message(f"No {doc_type} found for brick '{brick_name}'.")
            logger.log_info_message(f"This might be normal if the brick doesn't have any {doc_type} yet.")

        if existing_resources:
            if logger:
                logger.log_warning_message(
                    f"Marking {len(existing_resources)} existing {doc_type}(s) for deletion"
                )

            resource_ids = [r.id for r in existing_resources]
            deleted_count = CommunityDownloadService.mark_resources_for_deletion(
                resource_ids, logger
            )

            if logger:
                logger.log_success_message(f"Marked {deleted_count} {doc_type}(s) for deletion")
