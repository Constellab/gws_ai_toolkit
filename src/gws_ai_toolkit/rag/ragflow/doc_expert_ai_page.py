import streamlit as st
from gws_ai_toolkit.rag.ragflow.doc_expert_ai_page_state import (
    DocAiExpertPageState, DocAiExpertRagFlowDocument,
    DocExpertSelectedDocument)
from gws_core import OpenAiChat
from gws_core.streamlit import StreamlitContainers


def render_doc_expert_ai_page(state: DocAiExpertPageState):
    """
    Render the article AI page.
    """
    with StreamlitContainers.container_centered(key='article-ai-page'):
        col1, col2 = StreamlitContainers.columns_with_fit_content(key='article-header',
                                                                  cols=[1, 'fit-content'],
                                                                  vertical_align_items='center')
        with col1:
            st.title(state.config.page_emoji + " " + state.config.page_name)

        with col2:
            # reset button
            if st.button("Reset"):
                state.reset()

        status = state.get_status()
        if status == 'SEARCH':
            # Render the query form
            _render_query_form(state)
        elif status == "SEARCH_RESULTS":
            # Display search results
            _render_search_results(state)
        elif status == "DOCUMENT_CHAT":
            # Display document chat
            _render_document_chat(state)
        elif status == "DOCUMENT_SELECTED_NOT_LOADED":
            _load_chunks(state)


def _render_query_form(state: DocAiExpertPageState):
    with st.expander('Configuration'):
        dataset_id = st.text_input(
            "RagFlow Dataset ID",
            value=state.config.default_dataset_id,
            help="Enter the RagFlow dataset ID for the article AI"
        )
        if dataset_id:
            # Store dataset ID in state
            state.set_default_dataset_id(dataset_id)

        # RagFlow-specific parameters
        col1, col2 = st.columns(2)
        with col1:
            similarity_threshold = st.slider(
                "Similarity threshold",
                min_value=0.0,
                max_value=1.0,
                value=0.0,
                step=0.1,
                help="Minimum similarity threshold for chunk retrieval"
            )
            state.set_similarity_threshold(similarity_threshold)

        with col2:
            vector_similarity_weight = st.slider(
                "Vector similarity weight",
                min_value=0.0,
                max_value=1.0,
                value=0.3,
                step=0.1,
                help="Weight for vector similarity in hybrid search"
            )
            state.set_vector_similarity_weight(vector_similarity_weight)

        top_k = st.number_input(
            "Number of results",
            min_value=1,
            max_value=20,
            value=5,
            step=1,
            help="Number of top chunks to retrieve"
        )
        state.set_top_k(top_k)

    query = st.text_input(
        "Query",
        value="",
        help="Enter a query for the article AI"
    )

    if st.button("Search"):
        if not query:
            st.error("Please enter a query")
            return

        # Store query in state
        state.set_query(query)

        with st.spinner("Searching in documents..."):
            try:
                result = state.ragflow_service.retrieve_chunks(
                    dataset_id=state.get_default_dataset_id(),
                    query=query,
                    top_k=state.get_top_k(),
                    similarity_threshold=state.get_similarity_threshold(),
                    vector_similarity_weight=state.get_vector_similarity_weight()
                )

                if result and result.code == 0 and result.chunks:
                    # Store search results in state
                    state.set_documents_result(result)
                    st.rerun()
                else:
                    error_msg = result.message if result and result.code != 0 else "No results found"
                    st.error(error_msg)
                    return

            except Exception as e:
                st.error(f"Error searching documents: {str(e)}")
                return


def _render_search_results(state: DocAiExpertPageState):
    # Display search results
    st.subheader(f"Search Results for '{state.get_query()}'")
    result = state.get_documents_result()

    if result.chunks:
        # Group chunks by document
        documents = {}
        for chunk in result.chunks:
            doc_id = chunk.document_id
            doc_name = chunk.document_name
            if doc_id not in documents:
                documents[doc_id] = {
                    'id': doc_id,
                    'name': doc_name,
                    'chunks': []
                }
            documents[doc_id]['chunks'].append(chunk)

        st.write(f"**Found {len(documents)} documents with {len(result.chunks)} relevant chunks. Please select a document**")

        for doc_info in documents.values():
            col1, col2, col3 = st.columns([3, 1, 1])
            ragflow_document = DocAiExpertRagFlowDocument(
                id=doc_info['id'],
                name=doc_info['name'],
                dataset_id=state.get_default_dataset_id()
            )

            with col1:
                if st.button(f"{doc_info['name']} ({len(doc_info['chunks'])} chunks)", key=f"view_{doc_info['id']}"):
                    # Store selected document in state
                    state.set_selected_document(ragflow_document)
                    _load_chunks(state, doc_info['chunks'])
            with col2:
                if st.button("Download", key=f"download_{doc_info['id']}"):
                    _download_document(state, ragflow_document)
            with col3:
                st.text("")  # Empty space for alignment
    else:
        st.info("No documents found")


def _load_chunks(state: DocAiExpertPageState, chunks=None):
    """Load chunks for the selected document"""

    if chunks is None:
        # If chunks not provided, we need to retrieve them from search results
        selected_document = state.get_selected_document()
        result = state.get_documents_result()

        # Filter chunks for the selected document
        chunks = [chunk for chunk in result.chunks if chunk.document_id == selected_document.id]

    if not chunks:
        st.error("No chunks found for the selected document")
        return

    # Combine all chunk content
    document_content = "\n\n".join([chunk.content for chunk in chunks])

    # Summarize the document if summary prompt is configured
    summary = _summarize_document(state, document_content)

    selected_document = DocExpertSelectedDocument(
        chunks=chunks,
        content=document_content,
        summary=summary
    )

    # Store selected document in state
    state.set_selected_document_chunks(selected_document)
    st.rerun()


def _summarize_document(state: DocAiExpertPageState, document_content: str):
    """Summarize the document content"""
    summary_prompt = state.config.summary_prompt

    if not summary_prompt:
        return None

    if "[DOC_CONTENT]" not in summary_prompt:
        raise Exception(
            'The summary prompt must contain the [DOC_CONTENT] placeholder in the expert page configuration')

    with st.spinner("Summarizing document..."):
        # Replace the [DOC_CONTENT] placeholder with the document content
        summary_prompt = summary_prompt.replace(
            "[DOC_CONTENT]", document_content)

        chat = OpenAiChat()
        chat.add_user_message(summary_prompt)
        return chat.call_gpt()


def _render_document_chat(state: DocAiExpertPageState):
    """Render the document chat interface"""

    # Display document chat
    selected_document = state.get_selected_document()
    st.subheader(f"📄 {selected_document.name}")

    # Get chunks
    doc_chunk = state.get_selected_document_chunks()

    system_prompt = state.config.system_prompt

    if "[DOC_CONTENT]" not in system_prompt:
        raise Exception('The system prompt must contain the [DOC_CONTENT] placeholder in the expert page configuration')

    # Replace the [DOC_CONTENT] placeholder with the document content
    system_prompt = system_prompt.replace(
        "[DOC_CONTENT]", doc_chunk.content)

    streamlit_ai_chat = state.load_chat(system_prompt=system_prompt)

    with StreamlitContainers.row_container(key='document-action'):
        document_url = state.get_document_url(selected_document.id)
        if document_url:
            st.link_button('View document', document_url,
                           icon=':material/open_in_new:')

        if st.button("Download document", icon=':material/download:', key=f"download_{selected_document.id}"):
            _download_document(state, selected_document)

        if st.button("New chat", icon=':material/replay:', key='new_chat'):
            streamlit_ai_chat.reset()

    # Render the document summary
    if doc_chunk.summary:
        st.markdown('### 💡Document Summary')
        st.markdown(doc_chunk.summary)

    # Show chunk information
    with st.expander(f"📋 Document Chunks ({len(doc_chunk.chunks)})"):
        for i, chunk in enumerate(doc_chunk.chunks):
            st.markdown(f"**Chunk {i+1}** (Keywords: {', '.join(chunk.important_keywords)})")
            st.text(chunk.content_with_weight[: 200] + "..."
                    if len(chunk.content_with_weight) > 200 else chunk.content_with_weight)
            st.divider()

    st.divider()
    st.markdown('### 💬 Expert chat')

    # Display the chat messages
    streamlit_ai_chat.show_chat()

    if streamlit_ai_chat.last_message_is_user():
        with st.spinner('Processing...'):
            streamlit_ai_chat.call_gpt()
            # re-run the app
            st.rerun()

    user_prompt = st.chat_input(
        f"Ask a question about the document {selected_document.name}")

    if user_prompt:
        # add the message and rerun the app, so the message is shown before call to GPT
        streamlit_ai_chat.add_user_message(user_prompt)
        # re-run the app
        st.rerun()


def _download_document(state: DocAiExpertPageState, document: DocAiExpertRagFlowDocument):
    """
    Download a document and provide a download link.

    Args:
        document: RagFlow document to download
        state: Page state containing RagFlow service
    """
    with st.spinner("Preparing download for document..."):
        try:
            # Note: RagFlow doesn't have a direct download API like Dify
            # This is a placeholder implementation
            st.info("Document download is not available for RagFlow. Please access the document through the RagFlow interface.")

            # Alternative: Show document content for copy/paste
            doc_chunks = state.get_selected_document_chunks()
            if doc_chunks:
                st.text_area(
                    "Document content (you can copy this):",
                    doc_chunks.content,
                    height=300,
                    key=f"content_{document.id}"
                )

        except Exception as e:
            st.error(f"Error accessing document: {str(e)}")
