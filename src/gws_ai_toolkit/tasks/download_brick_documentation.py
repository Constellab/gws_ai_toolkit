import os

from gws_core import (
    ConfigParams,
    ConfigSpecs,
    EntityTagList,
    File,
    ResourceModel,
    ResourceOrigin,
    ResourceSearchBuilder,
    Scenario,
    StrParam,
    Tag,
    TagEntityType,
    TagService,
    Task,
    TaskInputs,
    TaskModel,
    TaskOutputs,
    task_decorator,
)
from gws_core.community.community_service import CommunityService
from gws_core.core.exception.exceptions.base_http_exception import BaseHTTPException
from gws_core.core.service.external_api_service import ExternalApiService
from gws_core.tag.entity_tag_list import EntityTagList
from gws_core.tag.tag import TagOrigins
from gws_core.tag.tag_entity_type import TagEntityType
from gws_core.user.current_user_service import CurrentUserService

from ..core.community_dto import BrickDocumentationDTO
from ..rag.common.rag_resource import RagResource
from ..services.community_download_service import CommunityDownloadService


@task_decorator(
    unique_name="DownloadBrickDocumentation",
    human_name="Download brick documentation files",
    short_description="Fetch and download markdown files for brick documentation from Constellab Community",
)
class DownloadBrickDocumentation(Task):
    """
    Fetch and download the markdown files for all documentation pages of a brick from the Constellab Community backend.

    This task fetches the list of documentation pages for a given brick, then downloads the markdown content
    for each documentation page. Each markdown file is stored and saved as an individual File resource.
    Files are tagged for later RAG processing.

    ## Usage
    - **Config**: Brick name (e.g., "gws_core", "gws_omix")
    - **Output**: None (Files are saved internally with tags)

    ## Notes
    - Fetches documentation list from: `/public/brick/all-docs/:brickName/latest`
    - Downloads each documentation from: `/documentation/download-doc-markdown/:docId`
    - Files are created with readable names (documentation titles)
    - Files are named using the documentation ID with a `.md` extension
    - If a documentation fails to download, it is skipped and logged as an error
    - Each File is tagged with:
      - `send_to_rag`: "CommunityDocumentations"
      - `community_brick_name`: brick name
      - `community_documentation_id`: documentation ID
      - `community_last_modificated_at`: last modification date

    ## Example
    Config:
    - brick_name: "gws_core"

    Saved Files:
    - File "Getting Started" with tags send_to_rag=CommunityDocumentations, community_brick_name=gws_core
    - File "API Reference" with tags send_to_rag=CommunityDocumentations, community_brick_name=gws_core
    - etc.
    """

    config_specs: ConfigSpecs = ConfigSpecs({
        "brick_name": StrParam(
            human_name="Brick name",
            short_description="Name of the brick to fetch documentation for (e.g., 'gws_core', 'gws_omix')",
            default_value="gws_core",
        ),
    })

    def run(self, params: ConfigParams, inputs: TaskInputs) -> TaskOutputs:
        """
        Fetch and download markdown files for all documentation pages of a brick.
        Each File is saved individually and tagged for RAG processing.

        :param params: Configuration parameters containing the brick name.
        :param inputs: Task inputs (none for this task).
        :return: Empty TaskOutputs.
        """
        brick_name = params.get_value("brick_name")
        self.log_info_message(f"Fetching documentation list for brick '{brick_name}'...")

        # Ensure tag keys exist
        tag_keys = [
            ("send_to_rag", "Send to RAG"),
            ("community_brick_name", "Community Brick Name"),
            ("community_documentation_id", "Community Documentation ID"),
            ("community_last_modificated_at", "Community Last Modified At"),
            ("delete_in_next_sync", "Delete in Next Sync"),
        ]
        CommunityDownloadService.ensure_tag_keys_exist(tag_keys, self)

        # Step 1: Fetch the list of documentations for the brick
        documentations = self._fetch_brick_documentations(brick_name)

        if not documentations:
            self.log_warning_message(f"No documentations found for brick '{brick_name}'.")
            return {}

        self.log_info_message(f"Found {len(documentations)} documentation page(s) for '{brick_name}'")

        # Get all existing Files for this brick to detect deletions
        existing_resources = CommunityDownloadService.get_existing_brick_files(
            brick_name, "CommunityDocumentations"
        )
        self.log_info_message(f"Found {len(existing_resources)} existing file(s) for brick '{brick_name}'")

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

        # Step 2: Download each documentation markdown file and save it
        for i, doc in enumerate(documentations):
            doc_id = doc.id
            doc_title = doc.title

            self.update_progress_value((i / len(documentations)) * 100, f"Processing '{doc_title}'")

            try:
                # Check if a File with this documentation ID already exists
                existing_resource = CommunityDownloadService.find_existing_resource_by_tag(
                    "community_documentation_id", doc_id
                )

                # Mark this resource as checked (still exists in Community)
                if existing_resource and existing_resource.id in resource_checked:
                    resource_checked[existing_resource.id] = True

                # Check if we need to update based on last_modified_at
                should_download, rag_tags_to_copy = CommunityDownloadService.should_update_resource(
                    existing_resource, doc.last_modified_at, self
                )

                if existing_resource:
                    if should_download:
                        self.log_info_message(
                            f"Updating '{doc_title}' - modified on {doc.last_modified_at}"
                        )
                    else:
                        self.log_info_message(
                            f"Skipping '{doc_title}' - already up-to-date (last modified: {doc.last_modified_at})"
                        )
                        skipped_count += 1

                if not should_download:
                    continue

                # Download the markdown file for this documentation
                self.log_info_message(f"Downloading '{doc_title}'...")
                markdown_content = self._download_documentation_markdown(doc_id)

                # Create a temporary file to store the markdown content
                tmp_dir = self.create_tmp_dir()
                file_path = os.path.join(tmp_dir, f"{doc_id}.md")
                with open(file_path, "w", encoding="utf-8") as f:
                    f.write(markdown_content)

                # Create a File resource
                file_resource = File(file_path)
                file_resource.name = doc_title  # Set a readable name

                # Add Community documentation tags to the resource's tag list
                file_resource.tags.add_tag(Tag("send_to_rag", "CommunityDocumentations"))
                file_resource.tags.add_tag(Tag("community_brick_name", brick_name))
                file_resource.tags.add_tag(Tag("community_documentation_id", doc.id))
                if doc.last_modified_at:
                    file_resource.tags.add_tag(Tag("community_last_modificated_at", doc.last_modified_at))

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
                    self.log_info_message(f"Deleting old version of '{doc_title}' (ID: {existing_resource.id})")
                    existing_resource.delete_instance()
                    updated_count += 1
                    self.log_success_message(
                        f"Updated '{doc_title}' (new ID: {file_model.id}) ({downloaded_count + updated_count}/{len(documentations)})"
                    )
                else:
                    downloaded_count += 1
                    self.log_success_message(
                        f"Downloaded and saved '{doc_title}' (ID: {file_model.id}) ({downloaded_count + updated_count}/{len(documentations)})"
                    )

            except BaseHTTPException as e:
                self.log_error_message(f"Failed to download '{doc_title}': HTTP {e.status_code} - {e.detail}")
                failed_count += 1
            except Exception as e:
                self.log_error_message(f"Failed to download '{doc_title}': {str(e)}")
                failed_count += 1

        # Step 3: Mark resources that no longer exist in Community for deletion
        unchecked_resource_ids = [rid for rid, checked in resource_checked.items() if not checked]
        deleted_count = CommunityDownloadService.mark_resources_for_deletion(
            unchecked_resource_ids, self
        )

        # Log summary
        summary_msg = (
            f"Download complete for brick '{brick_name}': "
            f"{downloaded_count} new, {updated_count} updated, {skipped_count} skipped, "
            f"{failed_count} failed out of {len(documentations)} total"
        )
        if deleted_count > 0:
            summary_msg += f", {deleted_count} marked for deletion"

        self.log_success_message(summary_msg)

        return {}

    def _fetch_brick_documentations(self, brick_name: str) -> list[BrickDocumentationDTO]:
        """
        Fetch the list of documentations for a specific brick from the Community backend.

        :param brick_name: The name of the brick.
        :return: List of BrickDocumentationDTO objects.
        :raises BaseHTTPException: If the API request fails.
        """
        route = f"/brick/all-docs/{brick_name}/latest"

        # Call the Community API to fetch the documentation list
        response = ExternalApiService.get(
            url=f"{CommunityService.get_community_api_url()}{route}",
            headers=CommunityService._get_request_header(),
        )

        # Parse the response and convert to DTOs
        response_data = response.json()

        documentations = [
            BrickDocumentationDTO.from_community_json_response(doc)
            for doc in response_data
        ]

        self.log_success_message(
            f"Successfully fetched {len(documentations)} documentation page(s) for brick '{brick_name}'"
        )
        return documentations

    def _download_documentation_markdown(self, doc_id: str) -> str:
        """
        Download the markdown content for a specific documentation page.

        :param doc_id: The ID of the documentation page.
        :return: The markdown content as a string.
        :raises BaseHTTPException: If the API request fails.
        """
        route = f"/documentation/download-doc-markdown/{doc_id}"

        # Call the Community API to download the markdown
        response = ExternalApiService.get(
            url=f"{CommunityService.get_community_api_url()}{route}",
            headers=CommunityService._get_request_header(),
            raise_exception_if_error=True,
        )

        return response.text
