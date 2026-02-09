import os

from gws_core import (
    ConfigParams,
    ConfigSpecs,
    EntityTagList,
    File,
    IntParam,
    JSONDict,
    OutputSpec,
    OutputSpecs,
    ResourceModel,
    Scenario,
    Tag,
    TagEntityType,
    Task,
    TaskInputs,
    TaskModel,
    TaskOutputs,
    task_decorator,
)
from gws_core.community.community_service import CommunityService
from gws_core.core.exception.exceptions.base_http_exception import BaseHTTPException
from gws_core.core.service.external_api_service import ExternalApiService

from ..core.community_dto import CommunityStoryDTO
from ..services.community_download_service import CommunityDownloadService


@task_decorator(
    unique_name="DownloadCommunityStories",
    human_name="Download Community stories",
    short_description="Fetch and download markdown files for Community stories",
)
class DownloadCommunityStories(Task):
    """
    Fetch and download the markdown files for all stories from the Constellab Community backend.

    This task fetches the list of stories (with pagination), then downloads the markdown content
    for each story. Each markdown file is stored and saved as an individual File resource.
    Files are tagged for later RAG processing.

    ## Usage
    - **Config**: Page size for pagination (default: 100)
    - **Output**: None (Files are saved internally with tags)

    ## Notes
    - Fetches story list from: `/story/filter?page={page}&size={size}` (POST)
    - Downloads each story from: `/story/story-markdown/:storyId`
    - Handles pagination automatically
    - Files are created with readable names (story titles)
    - If a story fails to download, it is skipped and logged as an error
    - Each File is tagged with:
      - `send_to_rag`: "CommunityStories"
      - `community_story_id`: story ID
      - `community_last_modificated_at`: last modification date

    ## Example
    Saved Files:
    - File "My Story" with tags send_to_rag=CommunityStories, community_story_id=xxx
    - etc.
    """

    config_specs: ConfigSpecs = ConfigSpecs({
        "page_size": IntParam(
            human_name="Page size",
            short_description="Number of stories to fetch per page",
            default_value=100,
            min_value=1,
            max_value=1000,
        ),
    })

    output_specs = OutputSpecs({
        "result": OutputSpec(
            JSONDict,
            human_name="Download result",
            short_description="Result of the download operation",
        ),
    })

    def run(self, params: ConfigParams, inputs: TaskInputs) -> TaskOutputs:
        """
        Fetch and download markdown files for all Community stories.
        Each File is saved individually and tagged for RAG processing.

        :param params: Configuration parameters.
        :param inputs: Task inputs (none for this task).
        :return: Empty TaskOutputs.
        """
        page_size = params.get_value("page_size")
        self.log_info_message(f"Fetching Community stories (page size: {page_size})...")

        # Ensure tag keys exist
        tag_keys = [
            ("send_to_rag", "Send to RAG"),
            ("community_story_id", "Community Story ID"),
            ("community_last_modificated_at", "Community Last Modified At"),
            ("delete_in_next_sync", "Delete in Next Sync"),
        ]
        CommunityDownloadService.ensure_tag_keys_exist(tag_keys, self)

        # Step 1: Fetch all stories (with pagination)
        stories = self._fetch_all_stories(page_size)

        # Get all existing Files for stories to detect deletions
        existing_resources = self._get_existing_story_files()
        self.log_info_message(f"Found {len(existing_resources)} existing story file(s)")

        # If no stories in Community but we have existing resources, mark them all for deletion
        if not stories:
            CommunityDownloadService.handle_no_documentation_case(
                existing_resources, "Community", "stories", self
            )
            return {"result": JSONDict({"is_finished": True})}

        self.log_info_message(f"Found {len(stories)} story/stories")

        # Track which resources are still valid (exist in Community)
        resource_checked = {resource.id: False for resource in existing_resources}

        # Get scenario and task model from the task context
        scenario_id = self.get_scenario_id()
        task_id = self.get_task_id()

        scenario = Scenario.get_by_id_and_check(scenario_id) if scenario_id else None
        task_model = TaskModel.get_by_id_and_check(task_id) if task_id else None

        downloaded_count = 0
        updated_count = 0
        skipped_count = 0
        failed_count = 0

        # Step 2: Download each story markdown file and save it
        for i, story in enumerate(stories):
            story_id = story.id
            story_title = story.title

            self.update_progress_value((i / len(stories)) * 100, f"Processing '{story_title}'")

            try:
                # Check if a File with this story ID already exists
                existing_resource = CommunityDownloadService.find_existing_resource_by_tag(
                    "community_story_id", story_id
                )

                # Mark this resource as checked (still exists in Community)
                if existing_resource and existing_resource.id in resource_checked:
                    resource_checked[existing_resource.id] = True

                # Check if we need to update based on last_modified_at
                should_download, rag_tags_to_copy = CommunityDownloadService.should_update_resource(
                    existing_resource, story.last_modified_at, self
                )

                if existing_resource:
                    if should_download:
                        self.log_info_message(
                            f"Updating '{story_title}' - modified on {story.last_modified_at}"
                        )
                    else:
                        self.log_info_message(
                            f"Skipping '{story_title}' - already up-to-date (last modified: {story.last_modified_at})"
                        )
                        skipped_count += 1

                if not should_download:
                    continue

                # Download the markdown file for this story
                self.log_info_message(f"Downloading '{story_title}'...")
                markdown_content = self._download_story_markdown(story_id)

                # Create a temporary file to store the markdown content
                tmp_dir = self.create_tmp_dir()
                file_path = os.path.join(tmp_dir, f"{story_id}.md")
                with open(file_path, "w", encoding="utf-8") as f:
                    f.write(markdown_content)

                # Create a File resource
                file_resource = File(file_path)
                file_resource.name = story_title  # Set a readable name

                # Add Community story tags to the resource's tag list
                file_resource.tags.add_tag(Tag("send_to_rag", "CommunityStories"))
                file_resource.tags.add_tag(Tag("community_story_id", story.id))
                if story.last_modified_at:
                    file_resource.tags.add_tag(Tag("community_last_modificated_at", story.last_modified_at))

                # Add copied RAG tags if updating an existing resource
                if rag_tags_to_copy:
                    for tag in rag_tags_to_copy:
                        file_resource.tags.add_tag(tag)

                # Save the File resource
                file_model = CommunityDownloadService.save_resource_with_context(
                    file_resource, scenario, task_model
                )

                # Delete the old resource if we were updating
                if existing_resource:
                    self.log_info_message(f"Deleting old version of '{story_title}' (ID: {existing_resource.id})")
                    existing_resource.delete_instance()
                    updated_count += 1
                    self.log_success_message(
                        f"Updated '{story_title}' (new ID: {file_model.id}) ({downloaded_count + updated_count}/{len(stories)})"
                    )
                else:
                    downloaded_count += 1
                    self.log_success_message(
                        f"Downloaded and saved '{story_title}' (ID: {file_model.id}) ({downloaded_count + updated_count}/{len(stories)})"
                    )

            except BaseHTTPException as e:
                self.log_error_message(f"Failed to download '{story_title}': HTTP {e.status_code} - {e.detail}")
                failed_count += 1
            except Exception as e:
                self.log_error_message(f"Failed to download '{story_title}': {str(e)}")
                failed_count += 1

        # Step 3: Mark resources that no longer exist in Community for deletion
        unchecked_resource_ids = [rid for rid, checked in resource_checked.items() if not checked]
        deleted_count = CommunityDownloadService.mark_resources_for_deletion(
            unchecked_resource_ids, self
        )

        # Log summary
        summary_msg = (
            f"Download complete: "
            f"{downloaded_count} new, {updated_count} updated, {skipped_count} skipped, "
            f"{failed_count} failed out of {len(stories)} total"
        )
        if deleted_count > 0:
            summary_msg += f", {deleted_count} marked for deletion"

        self.log_success_message(summary_msg)

        return {"result": JSONDict({"is_finished": True})}

    def _fetch_all_stories(self, page_size: int) -> list[CommunityStoryDTO]:
        """
        Fetch all stories from Community with pagination.

        :param page_size: Number of stories per page.
        :return: List of CommunityStoryDTO objects.
        """
        all_stories = []
        page = 0
        has_more = True

        while has_more:
            self.log_info_message(f"Fetching page {page} (size: {page_size})...")

            route = f"/story/filter?page={page}&size={page_size}"
            body = {
                "filters": {"title": None},
                "sorts": []
            }

            # Call the Community API to fetch the story list
            response = ExternalApiService.post(
                f"{CommunityService.get_community_api_url()}{route}",
                body,
                CommunityService._get_request_header(),
            )

            self.log_info_message(f"Response status code: {response.status_code}")

            # Parse the response
            response_data = response.json()

            self.log_info_message(f"Full response data: {response_data}")
            self.log_info_message(f"Response keys: {list(response_data.keys())}")

            # Get the paginated results
            objects = response_data.get("objects", [])
            total_elements = response_data.get("totalElements", 0)
            page_size_returned = response_data.get("pageSize", page_size)
            is_last = response_data.get("last", True)

            self.log_info_message(f"Total elements: {total_elements}, Page size: {page_size_returned}, Is last: {is_last}")
            self.log_info_message(f"Objects type: {type(objects)}, Objects length: {len(objects)}")

            if len(objects) > 0:
                self.log_info_message(f"First item sample: {objects[0]}")

            self.log_info_message(f"Received {len(objects)} story/stories from page {page}")

            # Convert to DTOs
            for story_data in objects:
                story = CommunityStoryDTO.from_community_json_response(story_data)
                all_stories.append(story)

            # Check if there are more pages
            page += 1
            has_more = not is_last

        self.log_success_message(f"Successfully fetched {len(all_stories)} story/stories in total")
        return all_stories

    def _download_story_markdown(self, story_id: str) -> str:
        """
        Download the markdown content for a specific story.

        :param story_id: The ID of the story.
        :return: The markdown content as a string.
        :raises BaseHTTPException: If the API request fails.
        """
        route = f"/story/story-markdown/{story_id}"

        # Call the Community API to download the markdown
        response = ExternalApiService.get(
            url=f"{CommunityService.get_community_api_url()}{route}",
            headers=CommunityService._get_request_header(),
            raise_exception_if_error=True,
        )

        return response.text

    def _get_existing_story_files(self) -> list[ResourceModel]:
        """
        Get all existing File resources for Community stories.

        :return: List of ResourceModel instances.
        """
        from gws_core import ResourceSearchBuilder

        search_builder = ResourceSearchBuilder()
        search_builder.add_tag_filter(Tag("send_to_rag", "CommunityStories"))
        search_builder.add_is_archived_filter(False)

        return search_builder.search_all()
