from typing import Any, Dict, List, Optional

from gws_core import Logger, ResourceModel
from pyparsing import abstractmethod

from gws_ai_toolkit.rag.common.rag_models import RagDocument

from .base_rag_service import BaseRagService
from .rag_resource import RagResource


class BaseRagAppService:
    """
    Abstract base class for the RagApp to interact with the Rag platform.
    """

    rag_service: BaseRagService
    dataset_id: str

    # Common constants
    CONSTELLAB_RESOURCE_ID_METADATA_KEY = "constellab_resource_id"

    def __init__(self, rag_service: BaseRagService, dataset_id: str) -> None:
        self.rag_service = rag_service
        self.dataset_id = dataset_id

    @abstractmethod
    def get_all_resources_to_send_to_rag(self) -> List[ResourceModel]:
        """Get all resources that need to be sent to Rag platform.
        The resource are then filtered to keep only compatible resources
        """

    def get_compatible_resource_explanation(self) -> str:
        """Get a text explaining how the filtration is done."""
        return f"""To be compatible with the Rag, the resource must:
- Be a File
- Be in one of the format : {RagResource.SUPPORTED_FILE_EXTENSIONS}
- Be smaller than {RagResource.MAX_FILE_SIZE_MB} MB
        """

    @abstractmethod
    def get_chat_default_filters(self) -> Dict[str, Any]:
        """Get the default inputs for the chat. This can be used to filter chat response."""

    def send_resource_to_rag(self, rag_resource: RagResource, upload_options: Any) -> None:
        """Send a resource to the RAG platform for processing.

        This method is responsible for sending a DatahubRagResource to the RAG platform
        for processing. It handles both the initial upload and updates to existing resources.

        Args:
            rag_resource (DatahubRagResource): The resource to send.
            upload_options (Any): Options for the upload, specific to the RAG platform.

        Raises:
            ValueError: If the resource is not compatible with RAG.
            e: If there is an error during the upload process.
            e: _description_
        """

        if rag_resource.is_compatible_with_rag() is False:
            raise ValueError("The resource is not compatible with Rag.")

        file = rag_resource.get_file()

        rag_uploaded_doc: RagDocument
        if rag_resource.is_synced_with_rag():
            # if the resource is already synced with rag, we need to update the document
            rag_uploaded_doc = self.rag_service.update_document_and_parse(
                file.path,
                self.dataset_id,
                rag_resource.get_and_check_document_id(),
                upload_options,
                filename=file.get_name(),
            )
        else:
            rag_uploaded_doc = self.rag_service.upload_document_and_parse(
                file.path, self.dataset_id, upload_options, filename=file.get_name()
            )

        try:
            metadata = self.get_document_metadata_before_sync(rag_resource)
            self.rag_service.update_document_metadata(
                self.dataset_id, rag_uploaded_doc.id, metadata
            )
        except Exception as e:
            Logger.error(
                f"Error while updating metadata for rag object {rag_resource.resource_model.id} after rag upload: {e}"
            )
            Logger.log_exception_stack_trace(e)
            # delete the document from Rag
            self.rag_service.delete_document(self.dataset_id, rag_uploaded_doc.id)
            raise e

        try:
            # Add the Rag document tag to the resource
            rag_resource.mark_resource_as_sent_to_rag(rag_uploaded_doc.id, self.dataset_id)
        except Exception as e:
            Logger.error(
                f"Error while adding tags to resource {rag_resource.resource_model.id} after rag upload: {e}"
            )
            Logger.log_exception_stack_trace(e)

            # delete the document from Rag
            self.rag_service.delete_document(self.dataset_id, rag_uploaded_doc.id)
            raise e

    def get_document_metadata_before_sync(self, rag_resource: RagResource) -> Dict[str, str]:
        """Method than can be overrided that is called before syncing a document.
        The returned metadata are set in the rag document
        """
        return {self.CONSTELLAB_RESOURCE_ID_METADATA_KEY: rag_resource.resource_model.id}

    def delete_resource_from_rag(self, rag_resource: RagResource) -> None:
        """Delete a resource from the RAG platform."""
        if rag_resource.is_synced_with_rag() is False:
            raise ValueError("The resource is not synced with RagFlow.")

        # Delete the resource from RagFlow
        self.rag_service.delete_document(
            rag_resource.get_dataset_base_id(), rag_resource.get_and_check_document_id()
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
            ragflow_resource = RagResource.from_document_id(ragflow_document.id)
            if ragflow_resource is None:
                document_to_delete.append(ragflow_document)

        return document_to_delete

    # Common methods
    def get_all_resource_to_sync(self) -> List[RagResource]:
        """Get all resources to sync with the platform."""
        resource_models = self.get_all_resources_to_send_to_rag()

        datahub_resources = []
        for resource_model in resource_models:
            resource = RagResource(resource_model)

            if resource.is_compatible_with_rag() and not resource.is_up_to_date_in_rag():
                datahub_resources.append(resource)

        return datahub_resources

    def get_all_synced_resources(self) -> List[RagResource]:
        """Get all resources synced with the platform."""
        resource_models = self.get_all_resources_to_send_to_rag()

        datahub_resources = []
        for resource_model in resource_models:
            resource = RagResource(resource_model)
            if resource.is_synced_with_rag():
                datahub_resources.append(resource)

        return datahub_resources

    def send_message_stream(
        self,
        query: str,
        conversation_id: Optional[str] = None,
        chat_id: Optional[str] = None,
        user_id: str | None = None,
        filters: Optional[Dict[str, Any]] = None,
    ):
        """Send a message stream.
        Override get_chat_default_filters to enable default filtering

        This method provides backward compatibility with the DataHub-specific messaging
        while using the abstracted RAG service underneath.

        Args:
            query: The user's query
            user: User identifier
            conversation_id: Optional conversation ID for context
            filters: Optional additional filters

        Returns:
            Generator yielding streaming responses
        """

        # get the default filters
        filtered_inputs = self.get_chat_default_filters() or {}

        if filters is not None:
            filtered_inputs.update(filters)

        # Use the underlying RAG service's chat_stream method
        return self.rag_service.chat_stream(
            query=query,
            user_id=user_id,
            conversation_id=conversation_id,
            chat_id=chat_id,
            inputs=filtered_inputs,
        )

    def get_rag_service(self) -> BaseRagService:
        """Get the RAG service."""
        return self.rag_service
