from typing import Optional

import reflex as rx
from gws_core import ResourceModel

from gws_ai_toolkit.rag.common.base_rag_app_service import BaseRagAppService
from gws_ai_toolkit.rag.common.rag_resource import RagResource

from ..chat_base.base_file_analysis_state import BaseFileAnalysisState
from ..rag_chat.config.rag_config_state import RagConfigState
from .ai_expert_config import AiExpertConfig
from .ai_expert_config_state import AiExpertConfigState


class AiExpertState(BaseFileAnalysisState, rx.State):
    """State management for AI Expert - specialized document-focused chat functionality.

    This state class manages the complete AI Expert workflow, providing intelligent
    conversation capabilities focused on a specific document. It integrates with
    OpenAI's API to provide document analysis, question answering, and interactive
    exploration of document content using multiple processing modes.

    Key Features:
        - Document-specific chat with full context awareness
        - Multiple processing modes (full_file, relevant_chunks, full_text_chunk)
        - OpenAI integration with streaming responses
        - File upload to OpenAI for advanced analysis
        - Document chunk retrieval and processing
        - Conversation history persistence
        - Error handling and user feedback

    Processing Modes:
        - full_file: Uploads entire document to OpenAI with code interpreter access
        - relevant_chunks: Retrieves only most relevant document chunks for the query
        - full_text_chunk: Includes all document chunks as text in the AI prompt

    State Attributes:
        current_doc_id (str): ID of the currently loaded document
        openai_file_id (Optional[str]): OpenAI file ID when document is uploaded
        _current_rag_resource (Optional[RagResource]): Loaded document resource
        _document_chunks_text (dict[int, str]): Cached document chunks by max_chunks

    Inherits from ChatStateBase providing:
        - Message management and streaming
        - Chat history and persistence
        - UI state management (title, placeholder, etc.)
        - Common chat functionality
    """

    # Document-specific context (inherits current_file_id from BaseFileAnalysisState)
    _current_rag_resource: Optional[RagResource] = None
    _document_chunks_text: dict[int, str] = {}

    # UI configuration
    title = "AI Expert"
    placeholder_text = "Ask about this document..."
    empty_state_message = "Start asking questions about this document"

    # Form state for configuration
    form_system_prompt: str = ""

    # Implementation of abstract methods from BaseFileAnalysisState
    def validate_resource(self, resource: ResourceModel) -> bool:
        """Validate if file is compatible with AI Expert analysis"""
        # For AI Expert, we use RagResource which handles compatibility
        rag_resource = RagResource(resource)
        return rag_resource.is_compatible_with_rag()

    async def get_config(self) -> AiExpertConfig:
        """Get AI Expert configuration"""
        app_config_state = await self.get_state(AiExpertConfigState)
        return await app_config_state.get_config()

    def get_analysis_type(self) -> str:
        """Return analysis type for history saving"""
        return "ai_expert"

    def _load_resource(self) -> Optional[ResourceModel]:
        # try to load from rag document id
        # Get the dynamic route parameter - different subclasses may use different parameter names
        document_id = self.document_id if hasattr(self, 'document_id') else None

        if not document_id:
            return None

        rag_resource = RagResource.from_document_id(document_id)
        if not rag_resource:
            # If that fails, try to load from resource id
            rag_resource = RagResource.from_resource_model_id(document_id)

        if not rag_resource:
            raise ValueError("Resource not found or not linked to RAG document")

        return rag_resource.resource_model

    async def call_ai_chat(self, user_message: str):
        """Get streaming response from OpenAI about the document with AI Expert specific modes"""
        client = self._get_openai_client()

        async with self:
            expert_config = await self.get_config()

        instructions: str = None
        tools: list = []

        if expert_config.mode == 'full_file':
            # Full file mode - use base class implementation
            return await super().call_ai_chat(user_message)

        elif expert_config.mode == 'relevant_chunks':
            # Relevant chunks mode - get only relevant chunks based on user question
            document_chunks = await self.get_relevant_document_chunks_text(user_message, expert_config.max_chunks)
            document_name = self._current_resource_model.name

            # Replace the placeholder with document name and include chunks
            system_prompt_with_chunks = expert_config.system_prompt.replace(
                expert_config.prompt_file_placeholder,
                f"{document_name}\n{document_chunks}"
            )

            instructions = system_prompt_with_chunks

        else:
            # Full text chunk mode - get all document chunks and include in prompt
            document_chunks = await self.get_document_chunks_text(expert_config.max_chunks)
            document_name = self._current_resource_model.name

            # Replace the placeholder with document name and include chunks
            system_prompt_with_chunks = expert_config.system_prompt.replace(
                expert_config.prompt_file_placeholder,
                f"{document_name}\n{document_chunks}"
            )

            instructions = system_prompt_with_chunks

        # For non-full_file modes, create streaming response without code interpreter
        with client.responses.stream(
            model=expert_config.model,
            instructions=instructions,
            input=[{"role": "user", "content": [{"type": "input_text", "text": user_message}]}],
            temperature=expert_config.temperature,
            previous_response_id=self.conversation_id,
            tools=tools,
        ) as stream:

            # Process streaming events (common for both modes)
            for event in stream:
                # Route events to specific handler methods
                if event.type == "response.output_text.delta":
                    await self.handle_output_text_delta(event)
                elif event.type == "response.code_interpreter_call_code.delta":
                    await self.handle_code_interpreter_call_code_delta(event)
                elif event.type == "response.output_text_annotation.added":
                    await self.handle_output_text_annotation_added(event)
                elif event.type == "response.output_item.added":
                    await self.close_current_message()
                elif event.type == "response.output_item.done":
                    await self.close_current_message()
                elif event.type == "response.created":
                    # Save the response ID for future conversation continuity
                    if hasattr(event, 'response') and hasattr(event.response, 'id'):
                        async with self:
                            self.conversation_id = event.response.id

            # Get the final response to extract response ID if not already captured
            final_response = stream.get_final_response()
            if final_response and hasattr(final_response, 'id') and not self.conversation_id:
                async with self:
                    self.set_conversation_id(final_response.id)

    # Event handlers are inherited from BaseFileAnalysisState - no need to duplicate

    async def get_document_chunks_text(self, max_chunks: int = 100) -> str:
        """Get the first max_chunks chunks of the document as text"""

        if max_chunks in self._document_chunks_text:
            return self._document_chunks_text[max_chunks]

        rag_app_service: BaseRagAppService
        async with self:
            rag_app_service = await self._get_rag_app_service()

        # Get the document ID from the resource
        document_id = (await self.get_current_rag_resource()).get_document_id()

        # Get the first max_chunks chunks
        chunks = rag_app_service.rag_service.get_document_chunks(
            dataset_id=rag_app_service.dataset_id,
            document_id=document_id,
            page=1,
            limit=max_chunks
        )

        if len(chunks) == 0:
            raise ValueError("No chunks found for this document")

        # Combine chunk contents into text
        chunk_texts = []
        for chunk in chunks:
            chunk_texts.append(chunk.content)

        async with self:
            self._document_chunks_text[max_chunks] = "\n".join(chunk_texts)
        return self._document_chunks_text[max_chunks]

    async def get_relevant_document_chunks_text(self, user_question: str, max_chunks: int = 5) -> str:
        """Get the most relevant chunks based on the user's question"""

        rag_app_service: BaseRagAppService
        async with self:
            rag_app_service = await self._get_rag_app_service()

        # Get the document ID from the resource
        document_id = (await self.get_current_rag_resource()).get_document_id()

        # Retrieve relevant chunks using the user's question
        chunks = rag_app_service.rag_service.retrieve_chunks(
            dataset_id=rag_app_service.dataset_id,
            query=user_question,
            top_k=max_chunks,
            document_ids=[document_id]
        )

        if len(chunks) == 0:
            raise ValueError("No relevant chunks found for this question")

        # Combine chunk contents into text
        chunk_texts = []
        for chunk in chunks:
            chunk_texts.append(chunk.content)

        return "\n".join(chunk_texts)

    # Override upload_file_to_openai to work with RagResource
    async def upload_file_to_openai(self) -> str:
        """Upload the document file to OpenAI and return file ID"""
        if self.openai_file_id:
            return self.openai_file_id

        client = self._get_openai_client()
        file = (await self.get_current_rag_resource()).get_file()

        # Upload file to OpenAI
        with open(file.path, "rb") as f:
            uploaded_file = client.files.create(
                file=f,
                purpose="assistants"
            )

        async with self:
            self.openai_file_id = uploaded_file.id

        return uploaded_file.id

    async def _get_rag_app_service(self) -> BaseRagAppService:
        """Get the RAG app service instance."""
        state: RagConfigState = await RagConfigState.get_instance(self)
        rag_app_service = await state.get_dataset_rag_app_service()
        if not rag_app_service:
            raise ValueError("RAG service not available")
        return rag_app_service

    async def get_current_rag_resource(self) -> RagResource:
        """Get the currently loaded RagResource"""
        if not self._current_rag_resource:
            resource_model = await self.get_current_resource_model()
            if not resource_model:
                raise ValueError("No resource loaded")
            self._current_rag_resource = RagResource(resource_model)
        return self._current_rag_resource

    def _after_chat_cleared(self):
        self._current_rag_resource = None
        self._document_chunks_text = {}
