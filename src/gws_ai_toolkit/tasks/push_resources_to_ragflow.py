from gws_core import (
    ConfigParams,
    ConfigSpecs,
    CredentialsDataOther,
    CredentialsParam,
    CredentialsType,
    EntityTagList,
    IntParam,
    JSONDict,
    OutputSpec,
    OutputSpecs,
    StrParam,
    Tag,
    TagEntityType,
    Task,
    TaskInputs,
    TaskOutputs,
    TypingStyle,
    task_decorator,
)

from gws_ai_toolkit.rag.common.rag_resource import RagResource
from gws_ai_toolkit.rag.common.tag_rag_app_service import TagRagAppService
from gws_ai_toolkit.rag.ragflow.ragflow_service import RagFlowService


@task_decorator(
    "PushResourcesToRagFlow",
    human_name="Push Resources to RagFlow",
    short_description="Push resources to RagFlow Dataset using tags",
    style=TypingStyle.community_image("ragflow", "#4A90E2"),
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
            default_value="send_to_rag",
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

        # Get all resources to send (filtered by tag)
        self.log_info_message(f"Searching for files with tag {tag_key}={tag_value}...")
        resource_models = tag_rag_service.get_all_resources_to_send_to_rag()
        total_files = len(resource_models)

        if total_files == 0:
            self.log_warning_message(f"No files found with tag {tag_key}={tag_value}")
            return {
                "upload_report": JSONDict({
                    "total_files": 0,
                    "uploaded_count": 0,
                    "failed_count": 0,
                    "dataset_id": dataset_id,
                    "tag_filter": f"{tag_key}={tag_value}",
                    "uploaded_documents": [],
                    "failed_documents": [],
                })
            }

        self.log_info_message(
            f"Found {total_files} file(s) to upload to RagFlow dataset {dataset_id}"
        )

        # Track results
        uploaded_count = 0
        failed_count = 0
        uploaded_documents = []
        failed_documents = []
        skipped_count = 0
        skipped_documents = []
        deleted_count = 0
        deleted_documents = []

        # Process each resource model
        for i, resource_model in enumerate(resource_models):
            # Check if we exceeded max errors
            if failed_count >= max_errors:
                self.log_error_message(
                    f"Maximum number of errors ({max_errors}) reached. Stopping upload."
                )
                break

            try:
                # Get the File resource from the model
                file_resource = resource_model.get_resource()
                file_name = file_resource.name or resource_model.id

                # Check if this resource is marked for deletion
                resource_tags = EntityTagList.find_by_entity(TagEntityType.RESOURCE, resource_model.id)
                delete_tag = resource_tags.get_first_tag_by_key("delete_in_next_sync")

                if delete_tag and delete_tag.get_tag_value() == "True":
                    # This resource should be deleted from RagFlow and the lab
                    self.log_info_message(
                        f"Deleting '{file_name}' - marked for deletion (no longer exists in Community)"
                    )

                    # Create RagResource wrapper to check if synced
                    rag_resource = RagResource(resource_model)

                    # Delete from RagFlow if it was synced
                    if rag_resource.is_synced_with_rag():
                        try:
                            document_id = rag_resource.get_document_id()
                            dataset_id_tag = resource_tags.get_first_tag_by_key(RagResource.RAG_DATASET_ID_TAG_KEY)
                            rag_dataset_id = dataset_id_tag.get_tag_value() if dataset_id_tag else dataset_id

                            self.log_info_message(
                                f"Deleting RagFlow document {document_id} for '{file_name}'..."
                            )
                            ragflow_service.delete_document(rag_dataset_id, document_id)
                        except Exception as e:
                            self.log_warning_message(
                                f"Could not delete RagFlow document for '{file_name}': {str(e)}"
                            )

                    # Delete the resource from the lab
                    resource_model.delete_instance()
                    deleted_count += 1
                    deleted_documents.append({
                        "resource_id": resource_model.id,
                        "resource_name": file_name,
                    })
                    self.log_success_message(f"Deleted '{file_name}' from RagFlow and lab")
                    continue

                # Create RagResource wrapper
                rag_resource = RagResource(resource_model)

                # Check if already synced
                is_updating = False
                old_document_id = None

                if rag_resource.is_synced_with_rag():
                    if rag_resource.is_up_to_date_in_rag():
                        self.log_info_message(
                            f"Skipping '{file_name}' - already synced and up-to-date"
                        )
                        skipped_count += 1
                        skipped_documents.append({
                            "resource_id": resource_model.id,
                            "resource_name": file_name,
                            "reason": "already_synced",
                        })
                        continue
                    else:
                        # File has RAG tags but is not up-to-date (has been modified)
                        # We need to delete the old document and upload a new one
                        is_updating = True
                        old_document_id = rag_resource.get_document_id()
                        self.log_info_message(
                            f"Updating '{file_name}' - file has been modified since last sync"
                        )

                # Check compatibility
                if not rag_resource.is_compatible_with_rag():
                    self.log_warning_message(
                        f"Skipping '{file_name}' - not compatible with RagFlow. "
                        f"Supported formats: {RagResource.SUPPORTED_FILE_EXTENSIONS}, "
                        f"Max size: {RagResource.MAX_FILE_SIZE_MB} MB"
                    )
                    skipped_count += 1
                    skipped_documents.append({
                        "resource_id": resource_model.id,
                        "resource_name": file_name,
                        "reason": "incompatible",
                    })
                    continue

                self.update_progress_value(
                    (i / total_files) * 100, f"Uploading '{file_name}'..."
                )

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

                # Mark resource as sent to RAG with tags (updates the tags with new doc ID and timestamp)
                rag_resource.mark_resource_as_sent_to_rag(uploaded_doc.id, dataset_id)

                # Record success
                uploaded_documents.append({
                    "resource_id": resource_model.id,
                    "resource_name": file_name,
                    "ragflow_document_id": uploaded_doc.id,
                    "was_update": is_updating,
                })

                uploaded_count += 1
                success_msg = f"Successfully {'updated' if is_updating else 'uploaded'} '{file_name}'"
                if is_updating:
                    success_msg += f" (old doc: {old_document_id}, new doc: {uploaded_doc.id})"
                self.log_success_message(
                    f"{success_msg} ({uploaded_count}/{total_files})"
                )

            except Exception as e:
                failed_count += 1
                error_msg = str(e)
                file_name = "Unknown"
                try:
                    file_name = resource_model.get_resource().name or resource_model.id
                except:
                    pass

                self.log_error_message(f"Failed to upload '{file_name}': {error_msg}")

                # Record failure
                failed_documents.append({
                    "resource_id": resource_model.id,
                    "resource_name": file_name,
                    "error": error_msg,
                })

        # Log final summary
        summary_msg = (
            f"Upload complete: {uploaded_count} uploaded, {skipped_count} skipped, "
            f"{failed_count} failed out of {total_files} total"
        )
        if deleted_count > 0:
            summary_msg += f", {deleted_count} deleted"

        self.log_info_message(summary_msg)

        # Create output report
        report_data = {
            "total_files": total_files,
            "uploaded_count": uploaded_count,
            "skipped_count": skipped_count,
            "deleted_count": deleted_count,
            "failed_count": failed_count,
            "dataset_id": dataset_id,
            "tag_filter": f"{tag_key}={tag_value}",
            "uploaded_documents": uploaded_documents,
            "skipped_documents": skipped_documents,
            "deleted_documents": deleted_documents,
            "failed_documents": failed_documents,
        }

        return {"upload_report": JSONDict(report_data)}
