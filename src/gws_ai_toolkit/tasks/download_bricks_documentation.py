import os

from gws_core import (
    BaseHTTPException,
    CommunityService,
    ConfigParams,
    ConfigSpecs,
    ExternalApiService,
    File,
    JSONDict,
    ListParam,
    OutputSpec,
    OutputSpecs,
    Scenario,
    Tag,
    Task,
    TaskInputs,
    TaskModel,
    TaskOutputs,
    task_decorator,
)

from ..core.community_dto import BrickDocumentationDTO, BrickTechnicalDocumentationDTO
from ..services.community_resource_files_manager_service import CommunityResourceFilesManagerService


@task_decorator(
    unique_name="DownloadBricksDocumentation",
    human_name="Download bricks documentation and technical documentation",
    short_description="Fetch and download all markdown files for bricks documentation and technical documentation from Constellab Community",
)
class DownloadBricksDocumentation(Task):
    """
    Fetch and download the markdown files for all documentation and technical documentation pages
    of multiple bricks from the Constellab Community backend.

    This task fetches both regular documentation and technical documentation for a list of bricks,
    then downloads the markdown content for each page. Each markdown file is stored and saved as
    an individual File resource. Files are tagged for later RAG processing.

    ## Usage
    - **Config**: List of brick names (e.g., ["gws_core", "gws_omix"])
    - **Output**: None (Files are saved internally with tags)

    ## Notes
    - Fetches documentation list from: `/brick/all-docs/:brickName/latest`
    - Fetches technical documentation list from: `/brick/all-technical-docs/:brickName/latest`
    - Downloads each documentation from: `/documentation/download-doc-markdown/:docId`
    - Downloads each technical doc from: `/documentation/download-tech-doc-markdown/:techDocType/:techDocId`
    - Files are created with readable names
    - If a documentation fails to download, it is skipped and logged as an error
    - Each documentation File is tagged with:
      - `send_to_rag`: "CommunityDocumentations"
      - `community_brick_name`: brick name
      - `community_documentation_id`: documentation ID
      - `community_last_modificated_at`: last modification date
    - Each technical documentation File is tagged with:
      - `send_to_rag`: "CommunityTechnicalDocumentations"
      - `community_brick_name`: brick name
      - `community_technical_documentation_id`: technical documentation ID
      - `community_tech_doc_type`: technical documentation type
      - `community_last_modificated_at`: last modification date

    ## Example
    Config:
    - brick_names: ["gws_core", "gws_omix"]

    Saved Files:
    - File "Getting Started" with tags send_to_rag=CommunityDocumentations, community_brick_name=gws_core
    - File "Resource Documentation" with tags send_to_rag=CommunityTechnicalDocumentations, community_brick_name=gws_core
    - etc.
    """

    config_specs: ConfigSpecs = ConfigSpecs({
        "brick_names": ListParam(
            human_name="Brick names",
            short_description="List of brick names to fetch documentation for (e.g., ['gws_core', 'gws_omix'])",
            default_value=["gws_core"],
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
        Fetch and download markdown files for all documentation pages of multiple bricks.
        Each File is saved individually and tagged for RAG processing.

        :param params: Configuration parameters containing the list of brick names.
        :param inputs: Task inputs (none for this task).
        :return: Empty TaskOutputs.
        """
        brick_names = params.get_value("brick_names")
        self.log_info_message(f"Processing documentation for {len(brick_names)} brick(s): {brick_names}")

        CommunityResourceFilesManagerService.ensure_tag_keys_exist(self)

        # Get scenario and task model from the task context
        scenario_id = self.get_scenario_id()
        task_id = self.get_task_id()

        scenario = Scenario.get_by_id_and_check(scenario_id) if scenario_id else None
        task_model = TaskModel.get_by_id_and_check(task_id) if task_id else None

        total_docs_downloaded = 0
        total_docs_updated = 0
        total_docs_skipped = 0
        total_docs_failed = 0
        total_techdocs_downloaded = 0
        total_techdocs_updated = 0
        total_techdocs_skipped = 0
        total_techdocs_failed = 0

        # Process each brick
        for brick_index, brick_name in enumerate(brick_names):
            self.log_info_message("")
            self.log_info_message(f"{'='*80}")
            self.log_info_message(f"Processing brick {brick_index + 1}/{len(brick_names)}: '{brick_name}'")
            self.log_info_message(f"{'='*80}")

            # Download regular documentation
            docs_stats = self._process_brick_documentation(brick_name, scenario, task_model)
            total_docs_downloaded += docs_stats['downloaded']
            total_docs_updated += docs_stats['updated']
            total_docs_skipped += docs_stats['skipped']
            total_docs_failed += docs_stats['failed']

            # Download technical documentation
            techdocs_stats = self._process_brick_technical_documentation(brick_name, scenario, task_model)
            total_techdocs_downloaded += techdocs_stats['downloaded']
            total_techdocs_updated += techdocs_stats['updated']
            total_techdocs_skipped += techdocs_stats['skipped']
            total_techdocs_failed += techdocs_stats['failed']

        # Log overall summary
        self.log_info_message("")
        self.log_info_message(f"{'='*80}")
        self.log_success_message(
            f"Overall Summary for {len(brick_names)} brick(s):\n"
            f"  Documentation: {total_docs_downloaded} new, {total_docs_updated} updated, "
            f"{total_docs_skipped} skipped, {total_docs_failed} failed\n"
            f"  Technical Documentation: {total_techdocs_downloaded} new, {total_techdocs_updated} updated, "
            f"{total_techdocs_skipped} skipped, {total_techdocs_failed} failed"
        )
        self.log_info_message(f"{'='*80}")

        return {"result": JSONDict({"is_finished": True})}

    def _process_brick_documentation(
        self,
        brick_name: str,
        scenario: Scenario | None,
        task_model: TaskModel | None
    ) -> dict:
        """
        Process regular documentation for a brick.

        :param brick_name: Name of the brick.
        :param scenario: Scenario context.
        :param task_model: Task model context.
        :return: Dictionary with download statistics.
        """
        self.log_info_message(f"Fetching documentation list for brick '{brick_name}'...")

        # Fetch the list of documentations for the brick
        documentations = self._fetch_brick_documentations(brick_name)

        # Get all existing Files for this brick to detect deletions
        existing_resources = CommunityResourceFilesManagerService.get_existing_brick_files(
            brick_name, "CommunityDocumentations"
        )
        self.log_info_message(f"Found {len(existing_resources)} existing documentation file(s) for brick '{brick_name}'")

        # If no docs in Community but we have existing resources, mark them all for deletion
        if not documentations:
            CommunityResourceFilesManagerService.handle_no_documentation_case(
                existing_resources, brick_name, "documentation", self
            )
            return {'downloaded': 0, 'updated': 0, 'skipped': 0, 'failed': 0}

        self.log_info_message(f"Found {len(documentations)} documentation page(s) for '{brick_name}'")

        # Track which resources are still valid (exist in Community)
        resource_checked = {resource.id: False for resource in existing_resources}

        downloaded_count = 0
        updated_count = 0
        skipped_count = 0
        failed_count = 0

        # Download each documentation markdown file and save it
        for doc in documentations:
            doc_id = doc.id
            doc_title = doc.title

            try:
                # Check if a File with this documentation ID already exists
                existing_resource = CommunityResourceFilesManagerService.find_existing_resource_by_tag(
                    "community_documentation_id", doc_id
                )

                # Mark this resource as checked (still exists in Community)
                if existing_resource and existing_resource.id in resource_checked:
                    resource_checked[existing_resource.id] = True

                # Check if we need to update based on last_modified_at
                should_download, rag_tags_to_copy = CommunityResourceFilesManagerService.should_update_resource(
                    existing_resource, doc.last_modified_at, self
                )

                if existing_resource:
                    if not should_download:
                        skipped_count += 1

                if not should_download:
                    continue
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
                file_resource.tags.add_tag(Tag(CommunityResourceFilesManagerService.SEND_TO_RAG_TAG_KEY, "CommunityDocumentations"))
                file_resource.tags.add_tag(Tag(CommunityResourceFilesManagerService.COMMUNITY_BRICK_NAME_TAG_KEY, brick_name))
                file_resource.tags.add_tag(Tag(CommunityResourceFilesManagerService.COMMUNITY_DOCUMENTATION_ID_TAG_KEY, doc.id))
                if doc.last_modified_at:
                    file_resource.tags.add_tag(Tag(CommunityResourceFilesManagerService.COMMUNITY_LAST_MODIFICATED_AT_TAG_KEY, doc.last_modified_at))

                # Add copied RAG tags if updating an existing resource
                if rag_tags_to_copy:
                    for tag in rag_tags_to_copy:
                        file_resource.tags.add_tag(tag)

                # Save the File resource
                file_model = CommunityResourceFilesManagerService.save_resource_with_context(
                    file_resource, scenario, task_model
                )

                # Delete the old resource if we were updating
                if existing_resource:
                    existing_resource.delete_instance()
                    updated_count += 1
                else:
                    downloaded_count += 1

            except BaseHTTPException as e:
                self.log_error_message(f"Failed to download '{doc_title}': HTTP {e.status_code} - {e.detail}")
                failed_count += 1
            except Exception as e:
                self.log_error_message(f"Failed to download '{doc_title}': {str(e)}")
                failed_count += 1

        # Mark resources that no longer exist in Community for deletion
        unchecked_resource_ids = [rid for rid, checked in resource_checked.items() if not checked]
        deleted_count = CommunityResourceFilesManagerService.mark_resources_for_deletion(
            unchecked_resource_ids, self
        )

        # Log summary for this brick
        summary_msg = (
            f"Documentation for brick '{brick_name}': "
            f"{downloaded_count} new, {updated_count} updated, {skipped_count} skipped, "
            f"{failed_count} failed out of {len(documentations)} total"
        )
        if deleted_count > 0:
            summary_msg += f", {deleted_count} marked for deletion"

        self.log_success_message(summary_msg)

        return {
            'downloaded': downloaded_count,
            'updated': updated_count,
            'skipped': skipped_count,
            'failed': failed_count
        }

    def _process_brick_technical_documentation(
        self,
        brick_name: str,
        scenario: Scenario | None,
        task_model: TaskModel | None
    ) -> dict:
        """
        Process technical documentation for a brick.

        :param brick_name: Name of the brick.
        :param scenario: Scenario context.
        :param task_model: Task model context.
        :return: Dictionary with download statistics.
        """
        self.log_info_message(f"Fetching technical documentation list for brick '{brick_name}'...")

        # Fetch the list of technical documentations for the brick
        tech_docs_by_type = self._fetch_brick_technical_documentations(brick_name)

        # Get all existing Files for this brick to detect deletions
        existing_resources = CommunityResourceFilesManagerService.get_existing_brick_files(
            brick_name, "CommunityTechnicalDocumentations"
        )
        self.log_info_message(f"Found {len(existing_resources)} existing technical documentation file(s) for brick '{brick_name}'")

        # If no technical docs in Community but we have existing resources, mark them all for deletion
        if not tech_docs_by_type:
            CommunityResourceFilesManagerService.handle_no_documentation_case(
                existing_resources, brick_name, "technical documentation", self
            )
            return {'downloaded': 0, 'updated': 0, 'skipped': 0, 'failed': 0}

        # Flatten all tech docs into a single list
        all_tech_docs = []
        for tech_doc_type, tech_docs in tech_docs_by_type.items():
            for tech_doc in tech_docs:
                all_tech_docs.append((tech_doc_type, tech_doc))

        self.log_info_message(f"Found {len(all_tech_docs)} technical documentation page(s) for '{brick_name}'")

        # Track which resources are still valid (exist in Community)
        resource_checked = {resource.id: False for resource in existing_resources}

        downloaded_count = 0
        updated_count = 0
        skipped_count = 0
        failed_count = 0

        # Download each technical documentation markdown file and save it
        for tech_doc_type, tech_doc in all_tech_docs:
            tech_doc_id = tech_doc.id
            tech_doc_name = tech_doc.human_name

            try:
                # Check if a File with this technical documentation ID already exists
                existing_resource = CommunityResourceFilesManagerService.find_existing_resource_by_tag(
                    "community_technical_documentation_id", tech_doc_id
                )

                # Mark this resource as checked (still exists in Community)
                if existing_resource and existing_resource.id in resource_checked:
                    resource_checked[existing_resource.id] = True

                # Check if we need to update based on last_modified_at
                should_download, rag_tags_to_copy = CommunityResourceFilesManagerService.should_update_resource(
                    existing_resource, tech_doc.last_modified_at, self
                )

                if existing_resource:
                    if not should_download:
                        skipped_count += 1

                if not should_download:
                    continue
                markdown_content = self._download_technical_documentation_markdown(
                    tech_doc_type, tech_doc_id, tech_doc_name
                )

                if not markdown_content:
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
                file_resource.tags.add_tag(Tag(CommunityResourceFilesManagerService.SEND_TO_RAG_TAG_KEY, "CommunityTechnicalDocumentations"))
                file_resource.tags.add_tag(Tag(CommunityResourceFilesManagerService.COMMUNITY_BRICK_NAME_TAG_KEY, brick_name))
                file_resource.tags.add_tag(Tag(CommunityResourceFilesManagerService.COMMUNITY_TECHNICAL_DOCUMENTATION_ID_TAG_KEY, tech_doc.id))
                file_resource.tags.add_tag(Tag(CommunityResourceFilesManagerService.COMMUNITY_TECH_DOC_TYPE_TAG_KEY, tech_doc_type))
                if tech_doc.last_modified_at:
                    file_resource.tags.add_tag(Tag(CommunityResourceFilesManagerService.COMMUNITY_LAST_MODIFICATED_AT_TAG_KEY, tech_doc.last_modified_at))

                # Add copied RAG tags if updating an existing resource
                if rag_tags_to_copy:
                    for tag in rag_tags_to_copy:
                        file_resource.tags.add_tag(tag)

                # Save the File resource
                file_model = CommunityResourceFilesManagerService.save_resource_with_context(
                    file_resource, scenario, task_model
                )

                # Delete the old resource if we were updating
                if existing_resource:
                    existing_resource.delete_instance()
                    updated_count += 1
                else:
                    downloaded_count += 1

            except BaseHTTPException as e:
                self.log_error_message(f"Failed to download '{tech_doc_name}': HTTP {e.status_code} - {e.detail}")
                failed_count += 1
            except Exception as e:
                self.log_error_message(f"Failed to download '{tech_doc_name}': {str(e)}")
                failed_count += 1

        # Mark resources that no longer exist in Community for deletion
        unchecked_resource_ids = [rid for rid, checked in resource_checked.items() if not checked]
        deleted_count = CommunityResourceFilesManagerService.mark_resources_for_deletion(
            unchecked_resource_ids, self
        )

        # Log summary for this brick
        summary_msg = (
            f"Technical documentation for brick '{brick_name}': "
            f"{downloaded_count} new, {updated_count} updated, {skipped_count} skipped, "
            f"{failed_count} failed out of {len(all_tech_docs)} total"
        )
        if deleted_count > 0:
            summary_msg += f", {deleted_count} marked for deletion"

        self.log_success_message(summary_msg)

        return {
            'downloaded': downloaded_count,
            'updated': updated_count,
            'skipped': skipped_count,
            'failed': failed_count
        }

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

        # Check if this is an error response
        if isinstance(response_data, dict) and 'status' in response_data and 'code' in response_data:
            self.log_error_message(f"API returned an error response: {response_data}")
            return []

        # Validate response is a list
        if not isinstance(response_data, list):
            self.log_error_message(
                f"Unexpected response format for brick '{brick_name}': expected list, got {type(response_data).__name__}"
            )
            return []

        documentations = []
        for doc in response_data:
            if not isinstance(doc, dict):
                self.log_warning_message(
                    f"Skipping invalid documentation entry for brick '{brick_name}': expected dict, got {type(doc).__name__}"
                )
                continue
            documentations.append(BrickDocumentationDTO.from_community_json_response(doc))

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

        # Explicitly decode as UTF-8 to preserve special characters and emojis
        return response.content.decode('utf-8')

    def _fetch_brick_technical_documentations(self, brick_name: str) -> dict[str, list[BrickTechnicalDocumentationDTO]]:
        """
        Fetch the list of technical documentation pages for a brick from Community.

        :param brick_name: Name of the brick.
        :return: Dict mapping techDocType to list of technical documentation DTOs.
        """
        route = f"/brick/all-technical-docs/{brick_name}/latest"
        full_url = f"{CommunityService.get_community_api_url()}{route}"

        # Call the Community API to fetch the technical documentation list
        response = ExternalApiService.get(
            url=full_url,
            headers=CommunityService._get_request_header(),
        )

        # Parse response: it's a dict with techDocType as keys
        response_data = response.json()

        # Check if this is an error response
        if isinstance(response_data, dict) and 'status' in response_data and 'code' in response_data:
            self.log_error_message(f"API returned an error response: {response_data}")
            return {}

        tech_docs_by_type = {}
        for tech_doc_type, tech_docs_data in response_data.items():
            tech_docs = []
            if isinstance(tech_docs_data, list):
                for tech_doc_data in tech_docs_data:
                    tech_doc = BrickTechnicalDocumentationDTO.from_community_json_response(
                        tech_doc_data, tech_doc_type
                    )
                    tech_docs.append(tech_doc)
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
        :param tech_doc_id: ID of the technical documentation.
        :param tech_doc_name: Name of the technical documentation (for logging).
        :return: The markdown content as a string, or None if download failed.
        """
        route = f"/documentation/download-tech-doc-markdown/{tech_doc_type}/{tech_doc_id}"
        full_url = f"{CommunityService.get_community_api_url()}{route}"

        try:
            # Call the Community API to download the markdown (don't raise exception to inspect response)
            response = ExternalApiService.get(
                url=full_url,
                headers=CommunityService._get_request_header(),
                raise_exception_if_error=False,
            )

            # Log detailed info about the response
            status_code = response.status_code
            if status_code < 200 or status_code >= 300:
                # Try to get the response body for debugging
                try:
                    response_body = response.text
                except Exception:
                    response_body = "<could not read response body>"

                self.log_error_message(
                    f"HTTP error downloading '{tech_doc_name}' (type: {tech_doc_type}, id: {tech_doc_id}):\n"
                    f"  URL: {full_url}\n"
                    f"  Status code: {status_code}\n"
                    f"  Response body: {response_body}"
                )
                return None

            # Explicitly decode as UTF-8 to preserve special characters and emojis
            content = response.content.decode('utf-8')

            if not content:
                self.log_error_message(
                    f"Empty content for '{tech_doc_name}' (type: {tech_doc_type}, id: {tech_doc_id}):\n"
                    f"  URL: {full_url}\n"
                    f"  Status code: {status_code}"
                )
                return None

            return content

        except BaseHTTPException as e:
            self.log_error_message(
                f"HTTP exception downloading '{tech_doc_name}' (type: {tech_doc_type}, id: {tech_doc_id}):\n"
                f"  URL: {full_url}\n"
                f"  Status code: {e.status_code}\n"
                f"  Detail: {e.detail}"
            )
            return None
        except Exception as e:
            self.log_error_message(
                f"Unexpected error downloading '{tech_doc_name}' (type: {tech_doc_type}, id: {tech_doc_id}):\n"
                f"  URL: {full_url}\n"
                f"  Error: {str(e)}"
            )
            return None
