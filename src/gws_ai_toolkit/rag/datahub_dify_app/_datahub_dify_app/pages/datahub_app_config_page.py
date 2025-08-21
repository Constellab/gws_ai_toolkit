from typing import List

import streamlit as st
from gws_ai_toolkit.rag.common.datahub_rag_resource import DatahubRagResource
from gws_ai_toolkit.rag.common.rag_models import RagDocument
from gws_ai_toolkit.rag.datahub_dify_app._datahub_dify_app.datahub_app_state import \
    DatahubRagAppState
from gws_core.impl.s3.datahub_s3_server_service import DataHubS3ServerService
from gws_core.streamlit import (StreamlitAuthenticateUser, StreamlitContainers,
                                StreamlitResourceSelect)


class PageState:

    SELECTED_RESOURCE_KEY = "selected_resource"

    @classmethod
    def get_selected_resource(cls) -> DatahubRagResource | None:
        """Get the selected resource from the session state."""
        return st.session_state.get(cls.SELECTED_RESOURCE_KEY)

    @classmethod
    def set_selected_resource(cls, resource: DatahubRagResource):
        """Set the selected resource in the session state."""
        st.session_state[cls.SELECTED_RESOURCE_KEY] = resource


def render_page():

    st.title("⚙️ Configuration")

    with StreamlitContainers.row_container('all_button_actions', gap='1em'):
        if st.button("Sync all resources", key='sync_all_resources'):
            _sync_all_resources_dialog()

        if st.button("Unsync all resources", key='unsync_all_resources'):
            _unsync_all_resources_dialog()
        if st.button('Delete expired documents', key='delete_expired_documents'):
            _delete_expired_documents()

    _render_sync_one_resource_section()


def _render_sync_one_resource_section():
    """Render the sync one resource section."""

    st.info("Search and select a resource to view its sync status and send it to the RAG platform.")
    selected_resource = PageState.get_selected_resource()
    selected_resource_id = selected_resource.resource_model.id if selected_resource else None

    resource_select = StreamlitResourceSelect()
    resource_select.add_tag_filter(DataHubS3ServerService.BUCKET_TAG_NAME, DataHubS3ServerService.FOLDERS_BUCKET_NAME)
    resource_select.include_not_flagged_resources()
    resource_model = resource_select.select_resource()
    # Uncomment for dev purpose
    # resource_model = ResourceModel.get_by_id_and_check('eb69aeda-a0be-4285-867b-b7d969247dee')

    # if the user selected a different resource, update the selected resource
    if resource_model and resource_model.id != selected_resource_id:
        PageState.set_selected_resource(DatahubRagResource(resource_model))
        st.rerun()

    if selected_resource is None:
        return

    if selected_resource.is_compatible_with_rag() is False:
        st.warning("The resource is not compatible with the RAG platform.")
        return

    if selected_resource.is_synced_with_rag():
        st.write("The resource is already sent to the RAG platform.")
        st.write(f"RAG knowledge base id: {selected_resource.get_dataset_id()}")
        st.write(f"RAG document id: {selected_resource.get_and_check_document_id()}")
        st.write(f"RAG sync date: {selected_resource.get_and_check_sync_date()}")

        with StreamlitContainers.row_container('resource_button_actions', gap='1em'):
            _render_send_to_rag_button(selected_resource, f"resend_{selected_resource_id}")
            if st.button("Delete from RAG"):
                datahub_rag_service = DatahubRagAppState.get_datahub_knowledge_rag_service()

                with st.spinner("Deleting resource from RAG..."):
                    datahub_rag_service.delete_resource_from_rag(selected_resource)
                    st.rerun()

    else:
        st.write("The resource is not sent to the RAG platform.")
        _render_send_to_rag_button(selected_resource, f"send_first_{selected_resource_id}")


def _render_send_to_rag_button(selected_resource: DatahubRagResource, key: str):
    """Render the send to RAG button."""
    if st.button("Send to RAG", key=key):
        datahub_rag_service = DatahubRagAppState.get_datahub_knowledge_rag_service()

        with st.spinner("Sending resource to RAG..."):
            datahub_rag_service.send_resource_to_rag(selected_resource,
                                                     set_folder_metadata=DatahubRagAppState.is_filter_rag_with_user_folders(),
                                                     upload_options=None)
            st.rerun()


@st.dialog("Sync all resources")
def _sync_all_resources_dialog():
    datahub_rag_service = DatahubRagAppState.get_datahub_knowledge_rag_service()
    resources: List[DatahubRagResource]
    with st.spinner("Retrieving resources to sync..."):
        resources = datahub_rag_service.get_all_resource_to_sync()

    st.write(f"Are you sure you want to sync {len(resources)} resources to the RAG platform? " +
             "It syncs only the resources that are not synced yet.")

    sync_buttons: bool = False

    with StreamlitContainers.row_container('sync_validation', gap='1em'):
        if st.button("Yes"):
            sync_buttons = True

        if st.button("No"):
            st.rerun()

    if sync_buttons:

        with StreamlitAuthenticateUser():
            my_bar = st.progress(0, text="Syncing resources...")

            has_error = False
            for i, rag_resource in enumerate(resources):

                try:
                    datahub_rag_service.send_resource_to_rag(rag_resource,
                                                             set_folder_metadata=DatahubRagAppState.is_filter_rag_with_user_folders(),
                                                             upload_options=None)
                except Exception as e:
                    st.error(
                        f"Error syncing resource '{rag_resource.resource_model.name}' {rag_resource.resource_model.id}: {e}")
                    has_error = True
                percent = int((i + 1) / len(resources) * 100)
                my_bar.progress(percent, text=f"Syncing resource {i + 1}/{len(resources)}")

        if not has_error:
            st.success("Resources synced successfully.")


@st.dialog("Unsync all resources")
def _unsync_all_resources_dialog():
    st.write("Are you sure you want to unsync all resources from the RAG platform?")

    unsync_buttons: bool = False
    with StreamlitContainers.row_container('unsync_validation', gap='1em'):
        if st.button("Yes"):
            unsync_buttons = True

        if st.button("No"):
            st.rerun()

    if unsync_buttons:
        datahub_rag_service = DatahubRagAppState.get_datahub_knowledge_rag_service()

        synced_resources: List[DatahubRagResource]
        with st.spinner("Retrieving synced resources..."):
            synced_resources = datahub_rag_service.get_all_synced_resources()

        with StreamlitAuthenticateUser():
            my_bar = st.progress(0, text="Unsyncing resources...")
            has_error = False
            for i, rag_resource in enumerate(synced_resources):
                try:
                    datahub_rag_service.delete_resource_from_rag(rag_resource)
                except Exception as e:
                    st.error(
                        f"Error unsyncing resource '{rag_resource.resource_model.name}' {rag_resource.resource_model.id}: {e}")
                    has_error = True
                percent = int((i + 1) / len(synced_resources) * 100)
                my_bar.progress(percent, text=f"Unsyncing resource {i + 1}/{len(synced_resources)}")

        if not has_error:
            st.success("Resources unsynced successfully.")


@st.dialog("Delete expired documents from RAG")
def _delete_expired_documents():
    datahub_rag_service = DatahubRagAppState.get_datahub_knowledge_rag_service()

    documents_to_delete: List[RagDocument]
    with st.spinner("Retrieving documents to delete..."):
        documents_to_delete = datahub_rag_service.get_rag_documents_to_delete()

    if not documents_to_delete:
        st.write("No documents to delete.")
        return

    st.write(
        f"Are you sure you want to delete {len(documents_to_delete)} documents from the RAG platform? Those documents were deleted from DataHub and are not synced with the RAG platform anymore.")

    with st.expander("Documents to delete"):
        st.json(RagDocument.to_json_list(documents_to_delete))

    delete_buttons: bool = False

    with StreamlitContainers.row_container('delete_validation', gap='1em'):
        if st.button("Yes"):
            delete_buttons = True

        if st.button("No"):
            st.rerun()

    if delete_buttons:
        with StreamlitAuthenticateUser():
            my_bar = st.progress(0, text="Deleting documents...")
            has_error = False
            for i, rag_document in enumerate(documents_to_delete):
                try:
                    datahub_rag_service.delete_rag_document(rag_document.id)
                except Exception as e:
                    st.error(
                        f"Error deleting document '{rag_document.name}' {rag_document.id}: {e}")
                    has_error = True
                percent = int((i + 1) / len(documents_to_delete) * 100)
                my_bar.progress(percent, text=f"Deleting document {i + 1}/{len(documents_to_delete)}")

        if not has_error:
            st.success("Documents deleted successfully.")
