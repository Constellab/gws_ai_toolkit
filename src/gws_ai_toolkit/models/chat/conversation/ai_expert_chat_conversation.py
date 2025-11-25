import io
import os
from collections.abc import Generator
from typing import Literal

from gws_core import BaseModelDTO, File, Logger
from openai import OpenAI
from openai.types.responses import ResponseCreatedEvent, ResponseOutputTextAnnotationAddedEvent
from PIL import Image

from gws_ai_toolkit.models import AllChatMessages
from gws_ai_toolkit.models.chat.message import ChatMessageError, ChatMessageImage, ChatMessageText
from gws_ai_toolkit.rag.common.base_rag_app_service import BaseRagAppService
from gws_ai_toolkit.rag.common.rag_resource import RagResource

from .base_chat_conversation import BaseChatConversation

AiExpertChatMode = Literal["full_text_chunk", "relevant_chunks", "full_file"]


class AiExpertConfig(BaseModelDTO):
    """Configuration class for AI Expert functionality."""

    prompt_file_placeholder: str = "[FILE]"

    system_prompt: str = """You are an AI expert assistant specialized in analyzing and answering questions about the document "[FILE]".

You have access to the full content of this document and can provide detailed, accurate answers based on the information contained within it.

When answering questions:
- Use only the document content to support your answers
- Be specific and cite relevant sections when possible
- If something is not covered in the document, clearly state this
- Provide thorough, helpful explanations

The user is asking questions specifically about this document, so focus your responses on the document's content and context."""

    mode: AiExpertChatMode = "full_file"
    max_chunks: int = 5
    model: str = "gpt-4o"
    temperature: float = 0.7


class AiExpertChatConversation(BaseChatConversation):
    """Chat conversation implementation for AI Expert document analysis.

    This class handles AI-powered document analysis conversations with streaming support,
    multiple processing modes, and OpenAI integration.

    Key Features:
        - Document-specific chat with full context awareness
        - Multiple processing modes (full_file, relevant_chunks, full_text_chunk)
        - OpenAI integration with streaming responses
        - File upload to OpenAI for advanced analysis
        - Document chunk retrieval and processing
        - Conversation persistence

    Processing Modes:
        - full_file: Uploads entire document to OpenAI with code interpreter access
        - relevant_chunks: Retrieves only most relevant document chunks for the query
        - full_text_chunk: Includes all document chunks as text in the AI prompt

    Attributes:
        config: Configuration for the AI chat (model, temperature, mode, etc.)
        rag_app_service: RAG service for chunk retrieval
        rag_resource: The document resource to analyze
        openai_file_id: OpenAI file ID after upload (for full_file mode)
    """

    config: AiExpertConfig
    rag_app_service: BaseRagAppService
    rag_resource: RagResource

    openai_file_id: str | None = None
    _document_chunks_text: dict[int, str]

    _previous_external_response_id: str | None = None
    _current_external_response_id: str | None = None

    def __init__(
        self, chat_app_name: str, config: AiExpertConfig, rag_app_service: BaseRagAppService, rag_resource: RagResource
    ) -> None:
        super().__init__(chat_app_name, config.to_json_dict(), "ai_expert")
        self.config = config
        self.rag_app_service = rag_app_service
        self.rag_resource = rag_resource
        self.openai_file_id = None
        self._document_chunks_text = {}
        self._previous_external_response_id = None
        self._current_external_response_id = None

    def _get_openai_client(self) -> OpenAI:
        """Get OpenAI client with API key."""
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise ValueError("OpenAI API key is not set")
        return OpenAI(api_key=api_key)

    def call_ai_chat(self, user_message: str) -> Generator[AllChatMessages, None, None]:
        """Handle user message and call AI chat service.

        Supports multiple processing modes:
        - full_file: Uploads document to OpenAI with code interpreter
        - relevant_chunks: Retrieves relevant chunks based on user question
        - full_text_chunk: Includes all document chunks in the prompt

        Args:
            user_message: The message from the user

        Yields:
            AllChatMessages: Messages as they are generated
        """
        client = self._get_openai_client()

        instructions: str = ""
        tools: list = []

        if self.config.mode == "full_file":
            # Full file mode - upload file to OpenAI
            file_id = self._upload_file_to_openai()
            document_name = self.rag_resource.resource_model.name

            instructions = self.config.system_prompt.replace(
                self.config.prompt_file_placeholder, f"{document_name}\n{file_id}"
            )
            tools = [{"type": "code_interpreter", "container": {"type": "auto", "file_ids": [file_id]}}]

        elif self.config.mode == "relevant_chunks":
            # Relevant chunks mode - get only relevant chunks based on user question
            document_chunks = self._get_relevant_document_chunks_text(user_message, self.config.max_chunks)
            document_name = self.rag_resource.resource_model.name

            instructions = self.config.system_prompt.replace(
                self.config.prompt_file_placeholder, f"{document_name}\n{document_chunks}"
            )

        else:
            # Full text chunk mode - get all document chunks and include in prompt
            document_chunks = self._get_document_chunks_text(self.config.max_chunks)
            document_name = self.rag_resource.resource_model.name

            instructions = self.config.system_prompt.replace(
                self.config.prompt_file_placeholder, f"{document_name}\n{document_chunks}"
            )

        # Create streaming response
        with client.responses.stream(
            model=self.config.model,
            instructions=instructions,
            input=[{"role": "user", "content": [{"type": "input_text", "text": user_message}]}],
            temperature=self.config.temperature,
            previous_response_id=self._previous_external_response_id,
            tools=tools,
        ) as stream:
            for event in stream:
                if event.type == "response.output_text.delta":
                    yield self.build_current_message(event.delta, external_id=self._current_external_response_id)

                elif event.type == "response.output_text.annotation.added":
                    message = self._handle_output_text_annotation_added(event, client)
                    if message:
                        yield message

                elif event.type == "response.output_item.added" or event.type == "response.output_item.done":
                    message = self.close_current_message(external_id=self._current_external_response_id)
                    if message:
                        yield message

                elif event.type == "response.created":
                    self._handle_response_created(event)

                elif event.type == "response.completed":
                    self._handle_response_completed()

        # Close any remaining message
        final_message = self.close_current_message(external_id=self._current_external_response_id)
        if final_message:
            yield final_message

    def _upload_file_to_openai(self) -> str:
        """Upload the file to OpenAI and return file ID."""
        if self.openai_file_id:
            return self.openai_file_id

        resource_model = self.rag_resource.resource_model
        if not resource_model:
            raise ValueError("No resource loaded")

        client = self._get_openai_client()
        file = resource_model.get_resource()

        if not isinstance(file, File):
            raise ValueError("Resource is not a file")

        with open(file.path, "rb") as f:
            uploaded_file = client.files.create(file=f, purpose="assistants")

        self.openai_file_id = uploaded_file.id
        return self.openai_file_id

    def _get_document_chunks_text(self, max_chunks: int = 100) -> str:
        """Get the first max_chunks chunks of the document as text."""
        if max_chunks in self._document_chunks_text:
            return self._document_chunks_text[max_chunks]

        document_id = self.rag_resource.get_document_id()

        chunks = self.rag_app_service.rag_service.get_document_chunks(
            dataset_id=self.rag_app_service.dataset_id, document_id=document_id, page=1, limit=max_chunks
        )

        if len(chunks) == 0:
            raise ValueError("No chunks found for this document")

        chunk_texts = [chunk.content for chunk in chunks]
        self._document_chunks_text[max_chunks] = "\n".join(chunk_texts)
        return self._document_chunks_text[max_chunks]

    def _get_relevant_document_chunks_text(self, user_question: str, max_chunks: int = 5) -> str:
        """Get the most relevant chunks based on the user's question."""
        document_id = self.rag_resource.get_document_id()

        chunks = self.rag_app_service.rag_service.retrieve_chunks(
            dataset_id=self.rag_app_service.dataset_id,
            query=user_question,
            top_k=max_chunks,
            document_ids=[document_id],
        )

        if len(chunks) == 0:
            raise ValueError("No relevant chunks found for this question")

        chunk_texts = [chunk.content for chunk in chunks]
        return "\n".join(chunk_texts)

    def _handle_response_created(self, event: ResponseCreatedEvent) -> None:
        """Handle response.created event."""
        self._current_external_response_id = event.response.id

    def _handle_response_completed(self) -> None:
        """Handle response.completed event."""
        if self._current_external_response_id:
            self._previous_external_response_id = self._current_external_response_id
            self._current_external_response_id = None

    def _handle_output_text_annotation_added(
        self, event: ResponseOutputTextAnnotationAddedEvent, client: OpenAI
    ) -> AllChatMessages | None:
        """Handle response.output_text.annotation.added event."""
        annotation = event.annotation

        if isinstance(annotation, dict) and "file_id" in annotation and "filename" in annotation:
            try:
                return self._extract_file_from_response(
                    annotation["file_id"], annotation["filename"], client, container_id=annotation.get("container_id")
                )
            except Exception as e:
                Logger.log_exception_stack_trace(e)
                error_message = ChatMessageError(
                    error=f"[Error loading file: {str(e)}]",
                    external_id=self._current_external_response_id,
                )
                return self._conversation_service.save_message(self._conversation.id, message=error_message)

        return None

    def _extract_file_from_response(
        self, file_id: str, filename: str, client: OpenAI, container_id: str | None = None
    ) -> AllChatMessages:
        """Extract file from OpenAI response - handles images and other files."""
        try:
            if file_id.startswith("cfile_") and container_id:
                file_data_binary = client.containers.files.content.retrieve(file_id, container_id=container_id)
            else:
                file_data_binary = client.files.content(file_id)

            file_extension = os.path.splitext(filename)[1].lower()

            if file_extension in [".png", ".jpg", ".jpeg", ".gif", ".bmp", ".webp"]:
                image_data = Image.open(io.BytesIO(file_data_binary.content))
                image_message = ChatMessageImage(image=image_data, external_id=self._current_external_response_id)

                return self._conversation_service.save_message(self._conversation.id, message=image_message)
            else:
                text_message = ChatMessageText(
                    content=f"File '{filename}' has been generated.",
                    external_id=self._current_external_response_id,
                )
                return self._conversation_service.save_message(self._conversation.id, message=text_message)

        except Exception as e:
            Logger.log_exception_stack_trace(e)
            raise ValueError(f"Error downloading file {file_id}: {str(e)}")
