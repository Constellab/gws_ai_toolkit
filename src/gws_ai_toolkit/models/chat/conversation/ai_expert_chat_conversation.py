import os
from collections.abc import Generator

from openai import OpenAI
from openai.types.responses import ResponseCreatedEvent

from gws_ai_toolkit.models.chat.conversation.ai_expert_chat_config import AiExpertChatConfig
from gws_ai_toolkit.models.chat.message.chat_message_types import ChatMessage
from gws_ai_toolkit.models.chat.message.chat_user_message import ChatUserMessageText
from gws_ai_toolkit.rag.common.base_rag_app_service import BaseRagAppService
from gws_ai_toolkit.rag.common.rag_resource import RagResource

from .base_chat_conversation import (
    BaseChatConversation,
    BaseChatConversationConfig,
    ChatConversationMode,
)


class AiExpertChatConversation(BaseChatConversation[ChatUserMessageText]):
    """Chat conversation implementation for AI Expert document analysis.

    This class handles AI-powered document analysis conversations with streaming support,
    multiple processing modes, and OpenAI integration.

    Key Features:
        - Document-specific chat with full context awareness
        - Multiple processing modes (relevant_chunks, full_text_chunk)
        - OpenAI integration with streaming responses
        - Document chunk retrieval and processing
        - Conversation persistence

    Processing Modes:
        - relevant_chunks: Retrieves only most relevant document chunks for the query
        - full_text_chunk: Includes all document chunks as text in the AI prompt

    Attributes:
        config: Configuration for the AI chat (model, temperature, mode, etc.)
        rag_app_service: RAG service for chunk retrieval
        rag_resource: The document resource to analyze
    """

    config: AiExpertChatConfig
    rag_app_service: BaseRagAppService
    rag_resource: RagResource

    _document_chunks_text: dict[int, str]

    _previous_external_response_id: str | None = None
    _current_external_response_id: str | None = None

    RESOURCE_ID_CONFIG_KEY = "resource_id"

    def __init__(
        self,
        config: BaseChatConversationConfig,
        chat_config: AiExpertChatConfig,
        rag_app_service: BaseRagAppService,
        rag_resource: RagResource,
    ) -> None:
        chat_configuration = chat_config.to_json_dict()
        # Store the resource ID so the conversation can be restored later
        chat_configuration[self.RESOURCE_ID_CONFIG_KEY] = rag_resource.get_id()
        super().__init__(
            config, mode=ChatConversationMode.AI_EXPERT.value, chat_configuration=chat_configuration
        )
        self.config = chat_config
        self.rag_app_service = rag_app_service
        self.rag_resource = rag_resource
        self._document_chunks_text = {}
        self._previous_external_response_id = None
        self._current_external_response_id = None

    def _get_openai_client(self) -> OpenAI:
        """Get OpenAI client with API key."""
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise ValueError("OpenAI API key is not set")
        return OpenAI(api_key=api_key)

    def _call_ai_chat(
        self, user_message: ChatUserMessageText
    ) -> Generator[ChatMessage, None, None]:
        """Handle user message and call AI chat service.

        Supports multiple processing modes:
        - relevant_chunks: Retrieves relevant chunks based on user question
        - full_text_chunk: Includes all document chunks in the prompt

        Args:
            user_message: The message from the user

        Yields:
            AllChatMessages: Messages as they are generated
        """

        client = self._get_openai_client()

        document_name = self.rag_resource.resource_model.name

        if self.config.mode == "relevant_chunks":
            # Relevant chunks mode - get only relevant chunks based on user question
            document_chunks = self._get_relevant_document_chunks_text(
                user_message.content, self.config.max_chunks
            )
        else:
            # Full text chunk mode - get all document chunks and include in prompt
            document_chunks = self._get_document_chunks_text(self.config.max_chunks)

        instructions = self.config.system_prompt.replace(
            self.config.prompt_file_placeholder, f"{document_name}\n{document_chunks}"
        )

        yield user_message

        # Create streaming response
        with client.responses.stream(
            model=self.config.model,
            instructions=instructions,
            input=[
                {"role": "user", "content": [{"type": "input_text", "text": user_message.content}]}
            ],
            temperature=self.config.temperature,
            previous_response_id=self._previous_external_response_id,
        ) as stream:
            for event in stream:
                if event.type == "response.output_text.delta":
                    yield self.build_current_message(
                        event.delta, external_id=self._current_external_response_id
                    )

                elif (
                    event.type == "response.output_item.added"
                    or event.type == "response.output_item.done"
                ):
                    message = self.close_current_message(
                        external_id=self._current_external_response_id
                    )
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

    def _get_document_chunks_text(self, max_chunks: int = 100) -> str:
        """Get the first max_chunks chunks of the document as text."""
        if max_chunks in self._document_chunks_text:
            return self._document_chunks_text[max_chunks]

        document_id = self.rag_resource.get_document_id()

        chunks = self.rag_app_service.rag_service.get_document_chunks(
            dataset_id=self.rag_app_service.dataset_id,
            document_id=document_id,
            page=1,
            limit=max_chunks,
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
