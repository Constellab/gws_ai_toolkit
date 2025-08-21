from typing import Generator, List, Optional, Union

from gws_ai_toolkit.rag.ragflow.datahub_ragflow_resource import \
    DatahubRagFlowResource
from gws_ai_toolkit.rag.ragflow.ragflow_class import (
    RagFlowChatEndStreamResponse, RagFlowChatStreamResponse, RagFlowDocument)
from gws_ai_toolkit.rag.ragflow.ragflow_service import RagFlowService
from gws_core import (DataHubS3ServerService, Logger, ResourceModel,
                      ResourceSearchBuilder)


class DatahubRagFlowService:

    ragflow_service: RagFlowService
    dataset_id: str

    RAGFLOW_ROOT_FOLDER_ID_METADATA_KEY = 'root_folder_id'
    RAGFLOW_CONSTELLAB_RESOURCE_ID_METADATA_KEY = 'constellab_resource_id'
    RAGFLOW_CHAT_INPUT_ACCESS_KEY = 'folder_'

    def __init__(self, ragflow_service: RagFlowService, dataset_id: str) -> None:
        self.ragflow_service = ragflow_service
        self.dataset_id = dataset_id

    def send_resource_to_ragflow(self, ragflow_resource: DatahubRagFlowResource) -> None:
        """Send a resource to RagFlow for processing."""

        if ragflow_resource.is_compatible_with_ragflow() is False:
            raise ValueError("The resource is not compatible with RagFlow.")

        root_folder = ragflow_resource.get_root_folder()
        if root_folder is None:
            raise ValueError("The resource does not have a folder.")

        file = ragflow_resource.get_file_path()

        ragflow_document: RagFlowDocument
        if ragflow_resource.is_synced_with_ragflow():
            # If the resource is already synced with RagFlow, we need to update the document
            ragflow_document = self.ragflow_service.update_document(
                file.path,
                self.dataset_id,
                ragflow_resource.get_and_check_ragflow_document_id(),
                filename=file.get_name()
            )
        else:
            ragflow_document = self.ragflow_service.upload_document(
                file.path,
                self.dataset_id,
                filename=file.get_name()
            )

        try:
            # Start parsing the document
            if ragflow_document:
                self.ragflow_service.parse_documents(self.dataset_id, [ragflow_document.id])
        except Exception as e:
            Logger.error(
                f"Error while starting document parsing for resource {ragflow_resource.resource_model.id} after RagFlow upload: {e}")
            Logger.log_exception_stack_trace(e)
            # Delete the document from RagFlow
            if ragflow_document:
                self.ragflow_service.delete_document(self.dataset_id, ragflow_document.id)
            raise e

        try:
            # Add the RagFlow document tag to the resource
            if ragflow_document:
                ragflow_resource.mark_resource_as_sent_to_ragflow(ragflow_document.id, self.dataset_id)
        except Exception as e:
            Logger.error(
                f"Error while adding tags to resource {ragflow_resource.resource_model.id} after RagFlow upload: {e}")
            Logger.log_exception_stack_trace(e)

            # Delete the document from RagFlow
            if ragflow_document:
                self.ragflow_service.delete_document(self.dataset_id, ragflow_document.id)
            raise e

    def delete_resource_from_ragflow(self, ragflow_resource: DatahubRagFlowResource) -> None:
        """Delete a resource from RagFlow."""
        if ragflow_resource.is_synced_with_ragflow() is False:
            raise ValueError("The resource is not synced with RagFlow.")

        # Delete the resource from RagFlow
        self.ragflow_service.delete_document(
            ragflow_resource.get_ragflow_dataset_id(),
            ragflow_resource.get_and_check_ragflow_document_id()
        )

        # Remove the tags from the resource
        ragflow_resource.unmark_resource_as_sent_to_ragflow()

    def delete_ragflow_document(self, ragflow_document_id: str) -> None:
        """Delete a document from RagFlow."""
        self.ragflow_service.delete_document(self.dataset_id, ragflow_document_id)

    def get_all_resource_to_sync(self) -> List[DatahubRagFlowResource]:
        """Get all resources to sync with RagFlow."""

        resource_models = self._get_compatible_resources()

        datahub_resources = []
        for resource_model in resource_models:
            # Check if the resource is compatible with RagFlow
            ragflow_resource = DatahubRagFlowResource(resource_model)

            if ragflow_resource.is_compatible_with_ragflow() and not ragflow_resource.is_up_to_date_in_ragflow():
                datahub_resources.append(ragflow_resource)

        return datahub_resources

    def get_all_synced_resources(self) -> List[DatahubRagFlowResource]:
        """Get all resources synced with RagFlow."""

        resource_models = self._get_compatible_resources()

        datahub_resources = []
        for resource_model in resource_models:
            # Check if the resource is compatible with RagFlow
            ragflow_resource = DatahubRagFlowResource(resource_model)
            if ragflow_resource.is_synced_with_ragflow():
                datahub_resources.append(ragflow_resource)

        return datahub_resources

    def _get_compatible_resources(self) -> List[ResourceModel]:
        """Get all resources compatible with RagFlow."""
        # Retrieve all the files stored in the datahub
        research_search = ResourceSearchBuilder()
        s3_service = DataHubS3ServerService.get_instance()
        research_search.add_tag_filter(s3_service.get_datahub_tag())
        research_search.add_is_fs_node_filter()
        research_search.add_is_archived_filter(False)
        research_search.add_has_folder_filter()

        return research_search.search_all()

    def get_ragflow_documents_to_delete(self) -> List[RagFlowDocument]:
        """List all the RagFlow documents that are not in the datahub anymore."""

        ragflow_documents = self.ragflow_service.get_all_documents(self.dataset_id)

        document_to_delete = []
        for ragflow_document in ragflow_documents:
            # Check if the resource is compatible with RagFlow
            ragflow_resource = DatahubRagFlowResource.from_ragflow_document_id(ragflow_document.id)
            if ragflow_resource is None:
                document_to_delete.append(ragflow_document)

        return document_to_delete

    #################################### CHAT ####################################

    def retrieve_chunks(self, query: str, top_k: int = 5,
                        similarity_threshold: float = 0.0, vector_similarity_weight: float = 0.3):
        """Retrieve relevant chunks from the RagFlow dataset.

        Args:
            user_root_folder_ids: List of root folder ID accessible by the user to limit the search
            query: The search query
            top_k: Number of top chunks to return
            similarity_threshold: Minimum similarity threshold
            vector_similarity_weight: Weight for vector similarity

        Returns:
            RagFlow retrieve response with chunks
        """
        # Note: RagFlow doesn't have the same folder-based access control as Dify
        # This method provides a simplified interface for chunk retrieval
        return self.ragflow_service.retrieve_chunks(
            dataset_id=self.dataset_id,
            query=query,
            top_k=top_k,
            similarity_threshold=similarity_threshold,
            vector_similarity_weight=vector_similarity_weight
        )

    def ask_question(
            self, chat_id: str,
            question: str, session_id: Optional[str] = None, stream: bool = True) -> Generator[
            Union[RagFlowChatStreamResponse, RagFlowChatEndStreamResponse],
            None, None]:
        """Ask a question to a RagFlow chat assistant.

        Args:
            chat_id: The RagFlow chat assistant ID
            user_root_folder_ids: List of root folder ID accessible by the user (for compatibility)
            question: The question to ask
            session_id: Optional session ID for conversation continuity
            stream: Whether to use streaming response

        Returns:
            Generator that yields response chunks
        """
        from gws_core.impl.ragflow.ragflow_class import RagFlowAskRequest

        ask_request = RagFlowAskRequest(
            question=question,
            stream=stream,
            session_id=session_id
        )

        # Call the RagFlow API with streaming
        return self.ragflow_service.ask(chat_id, ask_request)
