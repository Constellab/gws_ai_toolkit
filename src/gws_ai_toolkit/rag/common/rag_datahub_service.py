from typing import Any, Dict, List, Optional

from gws_ai_toolkit.rag.common.rag_models import RagDocument
from gws_core import (DataHubS3ServerService, Logger, ResourceModel,
                      ResourceSearchBuilder)

from .base_rag_service import BaseRagService
from .datahub_rag_resource import DatahubRagResource


class DatahubRagService():
    """
    Abstract base class for DataHub service wrappers that manage
    resource synchronization with RAG platforms.
    """

    rag_service: BaseRagService
    dataset_id: str

    # Common constants
    ROOT_FOLDER_ID_METADATA_KEY = 'root_folder_id'
    CONSTELLAB_RESOURCE_ID_METADATA_KEY = 'constellab_resource_id'
    CHAT_INPUT_ACCESS_KEY = 'folder_'

    def __init__(self, rag_service: BaseRagService, dataset_id: str) -> None:
        self.rag_service = rag_service
        self.dataset_id = dataset_id

    def send_resource_to_rag(self, rag_resource: DatahubRagResource, set_folder_metadata: bool,
                             upload_options: Any) -> None:
        """Send a resource to the RAG platform for processing.

        This method is responsible for sending a DatahubRagResource to the RAG platform
        for processing. It handles both the initial upload and updates to existing resources.

        Args:
            rag_resource (DatahubRagResource): The resource to send.
            set_folder_metadata (bool): Whether to set folder metadata into the rag document.
            upload_options (Any): Options for the upload, specific to the RAG platform.

        Raises:
            ValueError: If the resource is not compatible with Dify.
            ValueError: If the resource does not have a folder.
            e: If there is an error during the upload process.
            e: _description_
        """

        if rag_resource.is_compatible_with_rag() is False:
            raise ValueError("The resource is not compatible with Dify.")

        file = rag_resource.get_file()

        rag_uploaded_doc: RagDocument
        if rag_resource.is_synced_with_rag():
            # if the resource is already synced with dify, we need to update the document
            rag_uploaded_doc = self.rag_service.update_document_and_parse(file.path, self.dataset_id,
                                                                          rag_resource.get_and_check_document_id(),
                                                                          upload_options,
                                                                          filename=file.get_name())
        else:
            rag_uploaded_doc = self.rag_service.upload_document_and_parse(file.path, self.dataset_id, upload_options,
                                                                          filename=file.get_name())

        try:

            metadata = {
                self.CONSTELLAB_RESOURCE_ID_METADATA_KEY: rag_resource.resource_model.id
            }

            if set_folder_metadata:
                root_folder = rag_resource.get_root_folder()
                if root_folder is None:
                    raise ValueError("The resource does not have a folder.")
                metadata[self.ROOT_FOLDER_ID_METADATA_KEY] = root_folder.id

            self.rag_service.update_document_metadata(self.dataset_id, rag_uploaded_doc.id, metadata)
        except Exception as e:
            Logger.error(
                f"Error while updating metadata for dify object {rag_resource.resource_model.id} after dify upload: {e}")
            Logger.log_exception_stack_trace(e)
            # delete the document from Dify
            self.rag_service.delete_document(self.dataset_id, rag_uploaded_doc.id)
            raise e

        try:

            # Add the Dify document tag to the resource
            rag_resource.mark_resource_as_sent_to_rag(rag_uploaded_doc.id, self.dataset_id)
        except Exception as e:
            Logger.error(
                f"Error while adding tags to resource {rag_resource.resource_model.id} after dify upload: {e}")
            Logger.log_exception_stack_trace(e)

            # delete the document from Dify
            self.rag_service.delete_document(self.dataset_id, rag_uploaded_doc.id)
            raise e

    def delete_resource_from_rag(self, rag_resource: DatahubRagResource) -> None:
        """Delete a resource from the RAG platform."""
        if rag_resource.is_synced_with_rag() is False:
            raise ValueError("The resource is not synced with RagFlow.")

        # Delete the resource from RagFlow
        self.rag_service.delete_document(
            rag_resource.get_dataset_id(),
            rag_resource.get_and_check_document_id()
        )

        # Remove the tags from the resource
        rag_resource.unmark_resource_as_sent_to_rag()

    def delete_rag_document(self, rag_document_id: str) -> None:
        """Delete a document from the RAG platform."""
        self.rag_service.delete_document(self.dataset_id, rag_document_id)

    def get_rag_documents_to_delete(self) -> List[RagDocument]:
        """List all RAG documents that are not in the datahub anymore."""
        ragflow_documents = self.rag_service.get_all_documents(self.dataset_id)

        document_to_delete = []
        for ragflow_document in ragflow_documents:
            # Check if the resource is compatible with RagFlow
            ragflow_resource = DatahubRagResource.from_document_id(ragflow_document.id)
            if ragflow_resource is None:
                document_to_delete.append(ragflow_document)

        return document_to_delete

    # Common methods
    def get_all_resource_to_sync(self) -> List[DatahubRagResource]:
        """Get all resources to sync with the platform."""
        resource_models = self._get_compatible_resources()

        datahub_resources = []
        for resource_model in resource_models:
            resource = DatahubRagResource(resource_model)

            if resource.is_compatible_with_rag() and not resource.is_up_to_date_in_rag():
                datahub_resources.append(resource)

        return datahub_resources

    def get_all_synced_resources(self) -> List[DatahubRagResource]:
        """Get all resources synced with the platform."""
        resource_models = self._get_compatible_resources()

        datahub_resources = []
        for resource_model in resource_models:
            resource = DatahubRagResource(resource_model)
            if resource.is_synced_with_rag():
                datahub_resources.append(resource)

        return datahub_resources

    def _get_compatible_resources(self) -> List[ResourceModel]:
        """Get all resources compatible with the RAG platform."""
        research_search = ResourceSearchBuilder()
        s3_service = DataHubS3ServerService.get_instance()
        research_search.add_tag_filter(s3_service.get_datahub_tag())
        research_search.add_is_fs_node_filter()
        research_search.add_is_archived_filter(False)
        research_search.add_has_folder_filter()

        return research_search.search_all()

    def send_message_stream(self,
                            query: str,
                            conversation_id: Optional[str] = None,
                            chat_id: Optional[str] = None,
                            user_root_folder_ids: List[str] = None,
                            user: str = None,
                            inputs: Optional[Dict[str, Any]] = None):
        """Send a message stream with folder filtering support.

        This method provides backward compatibility with the DataHub-specific messaging
        while using the abstracted RAG service underneath.

        Args:
            user_root_folder_ids: List of folder IDs to filter by
            query: The user's query
            user: User identifier
            conversation_id: Optional conversation ID for context
            inputs: Optional additional inputs

        Returns:
            Generator yielding streaming responses
        """
        # For backward compatibility, we need to construct the appropriate inputs
        # that include folder filtering. This is platform-specific logic that was
        # previously handled in the Dify-specific service.

        # Prepare folder-based filtering inputs
        filtered_inputs = inputs or {}

        if user_root_folder_ids:
            # Add folder filtering to inputs - this format depends on how the
            # underlying RAG platform handles folder-based filtering
            folder_filter = {}
            for i, folder_id in enumerate(user_root_folder_ids):
                folder_filter[f"{self.CHAT_INPUT_ACCESS_KEY}{i}"] = folder_id
            filtered_inputs.update(folder_filter)

        # Use the underlying RAG service's chat_stream method
        return self.rag_service.chat_stream(
            query=query,
            user=user,
            conversation_id=conversation_id,
            chat_id=chat_id,
            inputs=filtered_inputs
        )
