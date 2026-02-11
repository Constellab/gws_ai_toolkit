from gws_ai_toolkit.rag.common.rag_resource import RagResource
from gws_ai_toolkit.rag.common.tag_rag_app_service import TagRagAppService
from gws_ai_toolkit.rag.ragflow.ragflow_service import RagFlowService
from gws_ai_toolkit.services.community_resource_files_manager_service import (
    CommunityResourceFilesManagerService,
)
from gws_core import (
    ConfigParams,
    ConfigSpecs,
    CredentialsDataOther,
    CredentialsParam,
    CredentialsType,
    InputSpec,
    InputSpecs,
    IntParam,
    JSONDict,
    OutputSpec,
    OutputSpecs,
    StrParam,
    Task,
    TaskInputs,
    TaskOutputs,
    task_decorator,
)


@task_decorator(
    "PushResourcesToRagFlow",
    human_name="Push Resources to RagFlow",
    short_description="Push resources to RagFlow Dataset using tags"
)
class PushResourcesToRagFlow(Task):
    """
    Push resources to RagFlow Dataset using tags.

    This task uses TagRagAppService to find all resources with specific tags,
    wraps each resource in a RagResource, uploads them to RagFlow, and marks them with appropriate sync tags.

    ## Features
    - Finds resources automatically using configurable tags
    - Validates resource compatibility with RagFlow (format, size)
    - Uploads documents and triggers parsing
    - Detects updates and replaces old documents
    - Handles deletion of resources marked with 'delete_in_next_sync' tag
    - Marks resources with RagFlow sync tags
    - Handles errors gracefully with configurable max error threshold
    - Returns detailed upload report

    ## Requirements
    - RagFlow API credentials (route + api_key)
    - RagFlow dataset ID where documents will be uploaded
    - Resources must be tagged with the specified tag_key and tag_value
    """

    input_specs = InputSpecs({
        "download_result": InputSpec(
            JSONDict,
            human_name="Download result",
            short_description="Optional input to indicate that download task is finished",
            optional=True,
        ),
    })

    output_specs = OutputSpecs({
        "upload_report": OutputSpec(
            JSONDict,
            human_name="Upload report",
            short_description="Detailed report of the upload operation",
        ),
    })

    config_specs = ConfigSpecs({
        "api_key": CredentialsParam(
            credentials_type=CredentialsType.OTHER,
            human_name="RagFlow API Key",
            short_description="A credentials that contains 'route' and 'api_key'",
        ),
        "dataset_id": StrParam(
            human_name="RagFlow dataset id",
            short_description="Id of the RagFlow dataset where to send the files",
        ),
        "tag_key": StrParam(
            human_name="Tag key",
            short_description="Tag key to filter resources to upload",
            default_value=CommunityResourceFilesManagerService.SEND_TO_RAG_TAG_KEY,
        ),
        "tag_value": StrParam(
            human_name="Tag value",
            short_description="Tag value to filter resources to upload",
            default_value="CommunityDocumentations",
        ),
        "max_errors": IntParam(
            human_name="Max errors",
            short_description="Maximum number of errors before stopping the upload",
            default_value=10,
            min_value=0,
            optional=True,
        ),
    })

    def run(self, params: ConfigParams, inputs: TaskInputs) -> TaskOutputs:
        """Run the task to push resources to RagFlow using TagRagAppService."""

        # Get config
        credentials: CredentialsDataOther = params.get_value("api_key")
        dataset_id = params.get_value("dataset_id")
        tag_key = params.get_value("tag_key")
        tag_value = params.get_value("tag_value")
        max_errors = params.get_value("max_errors")

        # Initialize RagFlow service
        ragflow_service = RagFlowService.from_credentials(credentials)

        # Initialize TagRagAppService to find files by tag
        tag_rag_service = TagRagAppService(
            rag_service=ragflow_service,
            dataset_id=dataset_id,
            additional_config={
                "tag_key": tag_key,
                "tag_value": tag_value,
            },
        )

        # Process deletions first
        deleted_results = self._process_deletions(tag_rag_service, ragflow_service, dataset_id)

        # Get all resources to upload (after deletions)
        self.log_info_message(f"Searching for files with tag {tag_key}={tag_value}...")
        resource_models = tag_rag_service.get_all_resources_to_send_to_rag()
        total_files = len(resource_models)

        if total_files == 0:
            self.log_warning_message(f"No files found with tag {tag_key}={tag_value}")
            return self._create_report(
                dataset_id, tag_key, tag_value, 0, [], [], [], deleted_results
            )

        self.log_info_message(
            f"Found {total_files} file(s) to upload to RagFlow dataset {dataset_id}"
        )

        # Process uploads
        upload_results = self._process_uploads(
            resource_models, ragflow_service, dataset_id, max_errors
        )

        # Log final summary
        self._log_summary(upload_results, deleted_results, total_files)

        # Create output report
        return self._create_report(
            dataset_id,
            tag_key,
            tag_value,
            total_files,
            upload_results["uploaded"],
            upload_results["skipped"],
            upload_results["failed"],
            deleted_results,
        )

    def _process_deletions(
        self, tag_rag_service: TagRagAppService, ragflow_service: RagFlowService, dataset_id: str
    ) -> list[dict]:
        """
        Process resources marked for deletion.

        Args:
            tag_rag_service: The tag RAG service
            ragflow_service: The RagFlow service
            dataset_id: The dataset ID

        Returns:
            list[dict]: List of deleted resource results
        """
        deleted_results = []

        # Get resources marked for deletion
        resources_to_delete = tag_rag_service.get_resources_marked_for_deletion()

        if not resources_to_delete:
            return deleted_results

        self.log_info_message(f"Found {len(resources_to_delete)} resource(s) marked for deletion")

        for resource_model in resources_to_delete:
            try:
                file_resource = resource_model.get_resource()
                file_name = file_resource.name or resource_model.id

                self.log_info_message(
                    f"Deleting '{file_name}' - marked for deletion (no longer exists in Community)"
                )

                # Use service method to handle deletion
                deletion_result = tag_rag_service.delete_resource_from_rag_and_lab(
                    resource_model, ragflow_service, dataset_id
                )

                deleted_results.append(deletion_result)

                if deletion_result["deleted_from_lab"]:
                    self.log_success_message(f"Deleted '{file_name}' from RagFlow and lab")
                else:
                    self.log_warning_message(
                        f"Failed to delete '{file_name}': {deletion_result.get('error', 'Unknown error')}"
                    )

            except Exception as e:
                self.log_error_message(f"Error processing deletion: {str(e)}")
                deleted_results.append({
                    "resource_id": resource_model.id,
                    "resource_name": "Unknown",
                    "deleted_from_rag": False,
                    "deleted_from_lab": False,
                    "error": str(e),
                })

        return deleted_results

    def _process_uploads(
        self,
        resource_models: list,
        ragflow_service: RagFlowService,
        dataset_id: str,
        max_errors: int,
    ) -> dict:
        """
        Process resource uploads to RagFlow.

        Args:
            resource_models: List of resource models to upload
            ragflow_service: The RagFlow service
            dataset_id: The dataset ID
            max_errors: Maximum number of errors before stopping

        Returns:
            dict: Upload results with uploaded, skipped, and failed lists
        """
        uploaded = []
        skipped = []
        failed = []
        total_files = len(resource_models)

        for i, resource_model in enumerate(resource_models):
            # Check if we exceeded max errors
            if len(failed) >= max_errors:
                self.log_error_message(
                    f"Maximum number of errors ({max_errors}) reached. Stopping upload."
                )
                break

            try:
                result = self._process_single_upload(
                    resource_model, ragflow_service, dataset_id, i, total_files
                )

                if result["status"] == "uploaded":
                    uploaded.append(result["data"])
                elif result["status"] == "skipped":
                    skipped.append(result["data"])
                elif result["status"] == "failed":
                    failed.append(result["data"])

            except Exception as e:
                failed.append(self._create_failure_result(resource_model, str(e)))

        return {"uploaded": uploaded, "skipped": skipped, "failed": failed}

    def _process_single_upload(
        self,
        resource_model,
        ragflow_service: RagFlowService,
        dataset_id: str,
        index: int,
        total: int,
    ) -> dict:
        """
        Process upload of a single resource.

        Args:
            resource_model: The resource model to upload
            ragflow_service: The RagFlow service
            dataset_id: The dataset ID
            index: Current index in the upload list
            total: Total number of resources

        Returns:
            dict: Result with status and data
        """
        # Get the File resource from the model
        file_resource = resource_model.get_resource()
        file_name = file_resource.name or resource_model.id

        # Create RagResource wrapper
        rag_resource = RagResource(resource_model)

        # Check if already synced and up-to-date
        if rag_resource.is_synced_with_rag() and rag_resource.is_up_to_date_in_rag():
            self.log_info_message(f"Skipping '{file_name}' - already synced and up-to-date")
            return {
                "status": "skipped",
                "data": {
                    "resource_id": resource_model.id,
                    "resource_name": file_name,
                    "reason": "already_synced",
                },
            }

        # Check compatibility
        if not rag_resource.is_compatible_with_rag():
            self.log_warning_message(
                f"Skipping '{file_name}' - not compatible with RagFlow. "
                f"Supported formats: {RagResource.SUPPORTED_FILE_EXTENSIONS}, "
                f"Max size: {RagResource.MAX_FILE_SIZE_MB} MB"
            )
            return {
                "status": "skipped",
                "data": {
                    "resource_id": resource_model.id,
                    "resource_name": file_name,
                    "reason": "incompatible",
                },
            }

        # Determine if updating or new upload
        is_updating = rag_resource.is_synced_with_rag() and not rag_resource.is_up_to_date_in_rag()
        old_document_id = rag_resource.get_document_id() if is_updating else None

        if is_updating:
            self.log_info_message(
                f"Updating '{file_name}' - file has been modified since last sync"
            )

        self.update_progress_value((index / total) * 100, f"Uploading '{file_name}'...")

        # Upload the resource
        uploaded_doc = self._upload_resource(
            rag_resource, ragflow_service, dataset_id, file_name, is_updating, old_document_id
        )

        # Record success
        success_msg = f"Successfully {'updated' if is_updating else 'uploaded'} '{file_name}'"
        if is_updating:
            success_msg += f" (old doc: {old_document_id}, new doc: {uploaded_doc.id})"
        self.log_success_message(success_msg)

        return {
            "status": "uploaded",
            "data": {
                "resource_id": resource_model.id,
                "resource_name": file_name,
                "ragflow_document_id": uploaded_doc.id,
                "was_update": is_updating,
            },
        }

    def _upload_resource(
        self,
        rag_resource: RagResource,
        ragflow_service: RagFlowService,
        dataset_id: str,
        file_name: str,
        is_updating: bool,
        old_document_id: str | None,
    ):
        """
        Upload a resource to RagFlow.

        Args:
            rag_resource: The RAG resource wrapper
            ragflow_service: The RagFlow service
            dataset_id: The dataset ID
            file_name: The file name
            is_updating: Whether this is an update
            old_document_id: The old document ID if updating

        Returns:
            Uploaded document
        """
        # Get the file to upload
        file = rag_resource.get_file()

        # If updating, delete the old document first
        if is_updating and old_document_id:
            try:
                self.log_info_message(
                    f"Deleting old RagFlow document {old_document_id} for '{file_name}'..."
                )
                ragflow_service.delete_document(dataset_id, old_document_id)
            except Exception as e:
                self.log_warning_message(
                    f"Could not delete old document {old_document_id}: {str(e)}. Proceeding with upload..."
                )

        # Upload document to RagFlow (new or replacement)
        action = "Updating" if is_updating else "Uploading"
        self.log_info_message(f"{action} '{file_name}' to RagFlow...")

        uploaded_doc = ragflow_service.upload_document(
            doc_paths=file.path,
            dataset_id=dataset_id,
            filename=file.get_name(),
        )

        # Parse the document
        self.log_info_message(f"Parsing document '{file_name}' in RagFlow...")
        ragflow_service.parse_documents(dataset_id, [uploaded_doc.id])

        # Mark resource as sent to RAG with tags
        rag_resource.mark_resource_as_sent_to_rag(uploaded_doc.id, dataset_id)

        return uploaded_doc

    def _create_failure_result(self, resource_model, error_msg: str) -> dict:
        """Create a failure result dict."""
        file_name = "Unknown"
        try:
            file_name = resource_model.get_resource().name or resource_model.id
        except Exception:
            pass

        self.log_error_message(f"Failed to upload '{file_name}': {error_msg}")

        return {
            "resource_id": resource_model.id,
            "resource_name": file_name,
            "error": error_msg,
        }

    def _log_summary(self, upload_results: dict, deleted_results: list, total_files: int) -> None:
        """Log a summary of the upload operation."""
        uploaded_count = len(upload_results["uploaded"])
        skipped_count = len(upload_results["skipped"])
        failed_count = len(upload_results["failed"])
        deleted_count = len(deleted_results)

        summary_msg = (
            f"Upload complete: {uploaded_count} uploaded, {skipped_count} skipped, "
            f"{failed_count} failed out of {total_files} total"
        )
        if deleted_count > 0:
            summary_msg += f", {deleted_count} deleted"

        self.log_info_message(summary_msg)

    def _create_report(
        self,
        dataset_id: str,
        tag_key: str,
        tag_value: str,
        total_files: int,
        uploaded: list,
        skipped: list,
        failed: list,
        deleted: list,
    ) -> TaskOutputs:
        """Create the output report."""
        report_data = {
            "total_files": total_files,
            "uploaded_count": len(uploaded),
            "skipped_count": len(skipped),
            "deleted_count": len(deleted),
            "failed_count": len(failed),
            "dataset_id": dataset_id,
            "tag_filter": f"{tag_key}={tag_value}",
            "uploaded_documents": uploaded,
            "skipped_documents": skipped,
            "deleted_documents": deleted,
            "failed_documents": failed,
        }

        return {"upload_report": JSONDict(report_data)}
