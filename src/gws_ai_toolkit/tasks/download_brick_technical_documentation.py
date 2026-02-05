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

from ..core.community_dto import BrickTechnicalDocumentationDTO
from ..rag.common.rag_resource import RagResource
from ..services.community_download_service import CommunityDownloadService


@task_decorator(
    unique_name="DownloadBrickTechnicalDocumentation",
    human_name="Download brick technical documentation files",
    short_description="Fetch and download markdown files for brick technical documentation from Constellab Community",
)
class DownloadBrickTechnicalDocumentation(Task):
    """
    Fetch and download the markdown files for all technical documentation pages of a brick from the Constellab Community backend.

    This task fetches the list of technical documentation pages for a given brick, then downloads the markdown content
    for each technical documentation page. Each markdown file is stored and saved as an individual File resource.
    Files are tagged for later RAG processing.

    ## Usage
    - **Config**: Brick name (e.g., "gws_core", "gws_omix")
    - **Output**: None (Files are saved internally with tags)

    ## Notes
    - Fetches technical documentation list from: `/public/brick/all-technical-docs/:brickName/latest`
    - Downloads each technical documentation from: `/documentation/download-tech-doc-markdown/:techDocType/:techDocId`
    - Files are created with readable names (documentation human names)
    - Files are named using the documentation unique name with a `.md` extension
    - If a documentation fails to download, it is skipped and logged as an error
    - Each File is tagged with:
      - `send_to_rag`: "CommunityTechnicalDocumentations"
      - `community_brick_name`: brick name
      - `community_technical_documentation_id`: documentation ID
      - `community_tech_doc_type`: technical documentation type
      - `community_last_modificated_at`: last modification date

    ## Example
    Config:
    - brick_name: "gws_core"

    Saved Files:
    - File "Resource documentation" with tags send_to_rag=CommunityTechnicalDocumentations, community_brick_name=gws_core
    - File "Task documentation" with tags send_to_rag=CommunityTechnicalDocumentations, community_brick_name=gws_core
    - etc.
    """

    config_specs: ConfigSpecs = ConfigSpecs({
        "brick_name": StrParam(
            human_name="Brick name",
            short_description="Name of the brick to fetch technical documentation for (e.g., 'gws_core', 'gws_omix')",
            default_value="gws_core",
        ),
    })

    def run(self, params: ConfigParams, inputs: TaskInputs) -> TaskOutputs:
        """
        Fetch and download markdown files for all technical documentation pages of a brick.
        Each File is saved individually and tagged for RAG processing.

        :param params: Configuration parameters containing the brick name.
        :param inputs: Task inputs (none for this task).
        :return: Empty TaskOutputs.
        """
        brick_name = params.get_value("brick_name")
        self.log_info_message(f"Fetching technical documentation list for brick '{brick_name}'...")

        # Ensure tag keys exist
        tag_keys = [
            ("send_to_rag", "Send to RAG"),
            ("community_brick_name", "Community Brick Name"),
            ("community_technical_documentation_id", "Community Technical Documentation ID"),
            ("community_tech_doc_type", "Community Tech Doc Type"),
            ("community_last_modificated_at", "Community Last Modified At"),
            ("delete_in_next_sync", "Delete in Next Sync"),
        ]
        CommunityDownloadService.ensure_tag_keys_exist(tag_keys, self)

        # Step 1: Fetch the list of technical documentations for the brick
        tech_docs_by_type = self._fetch_brick_technical_documentations(brick_name)

        # Get all existing Files for this brick to detect deletions
        existing_resources = CommunityDownloadService.get_existing_brick_files(
            brick_name, "CommunityTechnicalDocumentations"
        )
        self.log_info_message(f"Found {len(existing_resources)} existing technical documentation file(s) for brick '{brick_name}'")

        # If no technical docs in Community but we have existing resources, mark them all for deletion
        if not tech_docs_by_type:
            CommunityDownloadService.handle_no_documentation_case(
                existing_resources, brick_name, "technical documentation", self
            )
            return {}

        # Flatten the dict to get all tech docs
        all_tech_docs = []
        for tech_doc_type, tech_docs in tech_docs_by_type.items():
            for tech_doc in tech_docs:
                tech_doc.tech_doc_type = tech_doc_type
                all_tech_docs.append(tech_doc)

        self.log_info_message(f"Found {len(all_tech_docs)} technical documentation page(s) for '{brick_name}'")

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

        # Step 2: Download each technical documentation markdown file and save it
        for i, tech_doc in enumerate(all_tech_docs):
            tech_doc_id = tech_doc.id
            tech_doc_name = tech_doc.human_name
            tech_doc_type = tech_doc.tech_doc_type

            self.update_progress_value((i / len(all_tech_docs)) * 100, f"Processing '{tech_doc_name}'")

            try:
                # Check if a File with this technical documentation ID already exists
                existing_resource = CommunityDownloadService.find_existing_resource_by_tag(
                    "community_technical_documentation_id", tech_doc_id
                )

                # Mark this resource as checked (still exists in Community)
                if existing_resource and existing_resource.id in resource_checked:
                    resource_checked[existing_resource.id] = True

                # Check if we need to update based on last_modified_at
                should_download, rag_tags_to_copy = CommunityDownloadService.should_update_resource(
                    existing_resource, tech_doc.last_modified_at, self
                )

                if existing_resource:
                    if should_download:
                        self.log_info_message(
                            f"Updating '{tech_doc_name}' - modified on {tech_doc.last_modified_at}"
                        )
                    else:
                        self.log_info_message(
                            f"Skipping '{tech_doc_name}' - already up-to-date (last modified: {tech_doc.last_modified_at})"
                        )
                        skipped_count += 1

                if not should_download:
                    continue

                # Download the markdown file for this technical documentation
                self.log_info_message(f"Downloading '{tech_doc_name}' (type: {tech_doc_type})...")
                markdown_content = self._download_technical_documentation_markdown(tech_doc_type, tech_doc_id, tech_doc_name)

                if markdown_content is None:
                    failed_count += 1
                    continue

                # Create a temporary file to store the markdown content
                tmp_dir = self.create_tmp_dir()
                file_path = os.path.join(tmp_dir, f"{tech_doc.unique_name}.md")

                with open(file_path, "w", encoding="utf-8") as f:
                    f.write(markdown_content)

                # Create a File resource
                file_resource = File(file_path)
                file_resource.name = tech_doc_name  # Set a readable name

                # Add Community technical documentation tags to the resource's tag list
                file_resource.tags.add_tag(Tag("send_to_rag", "CommunityTechnicalDocumentations"))
                file_resource.tags.add_tag(Tag("community_brick_name", brick_name))
                file_resource.tags.add_tag(Tag("community_technical_documentation_id", tech_doc.id))
                file_resource.tags.add_tag(Tag("community_tech_doc_type", tech_doc_type))
                if tech_doc.last_modified_at:
                    file_resource.tags.add_tag(Tag("community_last_modificated_at", tech_doc.last_modified_at))

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
                    self.log_info_message(f"Deleting old version of '{tech_doc_name}' (ID: {existing_resource.id})")
                    existing_resource.delete_instance()
                    updated_count += 1
                    self.log_success_message(
                        f"Updated '{tech_doc_name}' (new ID: {file_model.id}) ({downloaded_count + updated_count}/{len(all_tech_docs)})"
                    )
                else:
                    downloaded_count += 1
                    self.log_success_message(
                        f"Downloaded and saved '{tech_doc_name}' (ID: {file_model.id}) ({downloaded_count + updated_count}/{len(all_tech_docs)})"
                    )

            except BaseHTTPException as e:
                self.log_error_message(f"Failed to download '{tech_doc_name}': HTTP {e.status_code} - {e.detail}")
                failed_count += 1
            except Exception as e:
                self.log_error_message(f"Failed to download '{tech_doc_name}': {str(e)}")
                failed_count += 1

        # Step 3: Check for resources that no longer exist in Community
        unchecked_resource_ids = [rid for rid, checked in resource_checked.items() if not checked]
        deleted_count = CommunityDownloadService.mark_resources_for_deletion(
            unchecked_resource_ids, self
        )

        # Log summary
        summary_msg = (
            f"Download complete for brick '{brick_name}': "
            f"{downloaded_count} new, {updated_count} updated, {skipped_count} skipped, "
            f"{failed_count} failed out of {len(all_tech_docs)} total"
        )
        if deleted_count > 0:
            summary_msg += f", {deleted_count} marked for deletion"

        self.log_success_message(summary_msg)

        return {}

    def _fetch_brick_technical_documentations(self, brick_name: str) -> dict[str, list[BrickTechnicalDocumentationDTO]]:
        """
        Fetch the list of technical documentation pages for a brick from Community.

        :param brick_name: Name of the brick.
        :return: Dict mapping techDocType to list of technical documentation DTOs.
        """
        route = f"/brick/all-technical-docs/{brick_name}/latest"
        full_url = f"{CommunityService.get_community_api_url()}{route}"

        self.log_info_message(f"Calling Community API: {full_url}")

        # Call the Community API to fetch the technical documentation list
        response = ExternalApiService.get(
            url=full_url,
            headers=CommunityService._get_request_header(),
        )

        self.log_info_message(f"Response status code: {response.status_code}")
        self.log_info_message(f"Response headers: {dict(response.headers)}")

        # Parse response: it's a dict with techDocType as keys
        response_data = response.json()

        self.log_info_message(f"Full response data: {response_data}")

        # Check if this is an error response
        if isinstance(response_data, dict) and 'status' in response_data and 'code' in response_data:
            self.log_error_message(f"API returned an error response: {response_data}")
            self.log_error_message(f"Status: {response_data.get('status')}, Code: {response_data.get('code')}")
            self.log_error_message(f"Detail: {response_data.get('detail')}")
            return {}

        self.log_info_message(f"Received response with {len(response_data)} tech doc type(s): {list(response_data.keys())}")

        tech_docs_by_type = {}
        for tech_doc_type, tech_docs_data in response_data.items():
            tech_docs = []
            if isinstance(tech_docs_data, list):
                self.log_info_message(f"Processing {len(tech_docs_data)} doc(s) for type '{tech_doc_type}'")
                for tech_doc_data in tech_docs_data:
                    tech_doc = BrickTechnicalDocumentationDTO.from_community_json_response(
                        tech_doc_data, tech_doc_type
                    )
                    tech_docs.append(tech_doc)
                    self.log_info_message(f"  - {tech_doc.human_name} (ID: {tech_doc.id})")
            else:
                self.log_warning_message(f"Unexpected data type for '{tech_doc_type}': {type(tech_docs_data)}")
            tech_docs_by_type[tech_doc_type] = tech_docs

        total_count = sum(len(docs) for docs in tech_docs_by_type.values())
        self.log_success_message(
            f"Successfully fetched {total_count} technical documentation page(s) for brick '{brick_name}'"
        )
        return tech_docs_by_type

    def _download_technical_documentation_markdown(self, tech_doc_type: str, tech_doc_id: str, tech_doc_name: str) -> str | None:
        """
        Download the markdown content for a technical documentation page.

        :param tech_doc_type: Type of the technical documentation.
        :param tech_doc_id: ID of the technical documentation to download.
        :param tech_doc_name: Name of the technical documentation (for logging).
        :return: Markdown content as a string, or None if download failed.
        """
        route = f"/documentation/download-tech-doc-markdown/{tech_doc_type}/{tech_doc_id}"

        # Call the Community API to download the markdown
        response = ExternalApiService.get(
            url=f"{CommunityService.get_community_api_url()}{route}",
            headers=CommunityService._get_request_header(),
            raise_exception_if_error=True,
        )

        return response.text
