import os
import uuid
from typing import Optional

import reflex as rx
from gws_ai_toolkit.rag.common.datahub_rag_resource import DatahubRagResource
from gws_ai_toolkit.rag.rag_app._rag_app.rag_app.components.generic_chat.chat_config import \
    ChatStateBase
from gws_ai_toolkit.rag.rag_app._rag_app.rag_app.components.generic_chat.generic_chat_class import \
    ChatMessage
from gws_core import (AuthenticateUser, GenerateShareLinkDTO,
                      ShareLinkEntityType, ShareLinkService)
from openai import OpenAI

from ...states.main_state import RagAppState


class AiExpertState(RagAppState, ChatStateBase):
    """State management for the AI Expert functionality - specialized chat for a specific document."""

    # Document context
    current_doc_id: str = ""
    openai_file_id: Optional[str] = None

    _current_rag_resource: Optional[DatahubRagResource] = None

    # UI configuration
    title = "AI Expert"
    placeholder_text = "Ask about this document..."
    empty_state_message = "Start asking questions about this document"

    def load_resource_from_url(self):
        """Handle page load - get resource ID from router state"""
        # The rag_doc_id should be automatically set by Reflex from the [rag_doc_id] route parameter
        # Access the dynamic route parameter directly - Reflex makes it available as self.rag_doc_id
        rag_doc_id = self.rag_doc_id if hasattr(self, 'rag_doc_id') else ""

        if self.current_doc_id and self.current_doc_id != rag_doc_id:
            # Reset chat if loading a different document
            self.clear_chat()

        if rag_doc_id and str(rag_doc_id).strip():
            self.load_resource(str(rag_doc_id))

    def _get_openai_client(self) -> OpenAI:
        """Get OpenAI client with API key"""
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise ValueError("OpenAI API key is not set")
        return OpenAI(api_key=api_key)

    def load_resource(self, rag_doc_id: str):
        """Load the resource from DataHub and prepare for chat"""
        if not self.check_authentication():
            return

        try:

            self.current_doc_id = rag_doc_id

            # Try to load the resource using document_id first
            rag_resource = None
            try:
                rag_resource = DatahubRagResource.from_document_id(rag_doc_id)
            except:
                # If that fails, try to load from resource id
                rag_resource = DatahubRagResource.from_resource_model_id(rag_doc_id)

            if not rag_resource:
                raise ValueError(f"Resource with ID {rag_doc_id} not found")

            if not rag_resource.is_compatible_with_rag():
                raise ValueError("Resource is not compatible with RAG")

            self._current_rag_resource = rag_resource

            self.subtitle = rag_resource.resource_model.name

        except Exception as e:
            error_message = ChatMessage(
                role="assistant",
                content=f"Error loading document: {str(e)}",
                id=str(uuid.uuid4()),
                sources=[]
            )

            self.chat_messages.append(error_message)

    async def call_ai_chat(self, user_message: str):
        """Get streaming response from OpenAI about the document"""

        client = self._get_openai_client()

        uploaded_file_id = await self.upload_file_to_openai()

        system_prompt = self._get_system_prompt(uploaded_file_id)

        # Create streaming response using new Responses API
        with client.responses.stream(
            model="gpt-4o",
            instructions=system_prompt,
            input=[{"role": "user", "content": [{"type": "input_text", "text": user_message}]}],
            temperature=0.7,
            tools=[{"type": "code_interpreter", "container": {"type": "auto", "file_ids": [uploaded_file_id]}}],
            previous_response_id=self.conversation_id,
        ) as stream:

            # Process streaming events
            for event in stream:
                # Route events to specific handler methods
                if event.type == "response.output_text.delta":
                    await self.handle_output_text_delta(event)
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

    async def handle_output_text_delta(self, event):
        """Handle response.output_text.delta event"""
        text = event.delta

        current_message: Optional[ChatMessage] = None

        async with self:
            current_message = self.current_response_message

        if current_message:
            async with self:
                current_message.content += text
        else:
            # Create new message if none exists
            new_message = ChatMessage(
                role="assistant",
                content=text,
                id=str(uuid.uuid4()),
                sources=[]
            )
            await self.update_current_response_message(new_message)

    async def upload_file_to_openai(self) -> str:
        """Upload the document file to OpenAI and return file ID"""
        if self.openai_file_id:
            return self.openai_file_id

        client = self._get_openai_client()

        file = self._current_rag_resource.get_file()

        # Upload file to OpenAI
        with open(file.path, "rb") as f:
            uploaded_file = client.files.create(
                file=f,
                purpose="assistants"
            )

        async with self:
            self.openai_file_id = uploaded_file.id

        return uploaded_file.id

    def _get_system_prompt(self, uploaded_file_id: str) -> str:
        """Get the system prompt for the AI expert"""
        return f"""You are an AI expert assistant specialized in analyzing and answering questions about the document "{uploaded_file_id}".

You have access to the full content of this document and can provide detailed, accurate answers based on the information contained within it.

When answering questions:
- Use only the document content to support your answers
- Be specific and cite relevant sections when possible
- If something is not covered in the document, clearly state this
- Provide thorough, helpful explanations

The user is asking questions specifically about this document, so focus your responses on the document's content and context."""

    @rx.event
    async def redirect_to_document(self):
        """Redirect the user to an external URL."""

        # Generate a public share link for the document
        generate_link_dto = GenerateShareLinkDTO.get_1_hour_validity(
            entity_id=self._current_rag_resource.get_id(),
            entity_type=ShareLinkEntityType.RESOURCE
        )

        with AuthenticateUser(self.get_and_check_current_user()):
            share_link = ShareLinkService.get_or_create_valid_public_share_link(generate_link_dto)

        if share_link:
            # Redirect the user to the share link URL
            return rx.redirect(share_link.get_public_link(), is_external=True)
