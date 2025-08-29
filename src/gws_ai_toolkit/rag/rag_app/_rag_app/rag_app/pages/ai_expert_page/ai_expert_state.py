import io
import os
from typing import Optional, Union

import reflex as rx
from gws_ai_toolkit.rag.common.rag_resource import RagResource
from gws_ai_toolkit.rag.rag_app._rag_app.rag_app.components.app_config.ai_expert_config import \
    AiExpertConfig
from gws_ai_toolkit.rag.rag_app._rag_app.rag_app.components.app_config.app_config_state import \
    AppConfigState
from gws_ai_toolkit.rag.rag_app._rag_app.rag_app.components.generic_chat.chat_config import \
    ChatStateBase
from gws_ai_toolkit.rag.rag_app._rag_app.rag_app.components.generic_chat.generic_chat_class import (
    ChatMessage, ChatMessageImage, ChatMessageText)
from gws_core.core.utils.logger import Logger
from openai import OpenAI
from PIL import Image

from ...states.main_state import RagAppState


class AiExpertState(RagAppState, ChatStateBase):
    """State management for the AI Expert functionality - specialized chat for a specific document."""

    # Document context
    current_doc_id: str = ""
    openai_file_id: Optional[str] = None

    _current_rag_resource: Optional[RagResource] = None

    # UI configuration
    title = "AI Expert"
    placeholder_text = "Ask about this document..."
    empty_state_message = "Start asking questions about this document"

    # Form state for configuration
    form_system_prompt: str = ""

    async def load_resource_from_url(self):
        """Handle page load - get resource ID from router state"""
        # The rag_doc_id should be automatically set by Reflex from the [rag_doc_id] route parameter
        # Access the dynamic route parameter directly - Reflex makes it available as self.rag_doc_id
        rag_doc_id = self.rag_doc_id if hasattr(self, 'rag_doc_id') else ""

        if self.current_doc_id and self.current_doc_id != rag_doc_id:
            # Reset chat if loading a different document
            self.clear_chat()

        if rag_doc_id and str(rag_doc_id).strip():
            await self.load_resource(str(rag_doc_id))

    def _get_openai_client(self) -> OpenAI:
        """Get OpenAI client with API key"""
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise ValueError("OpenAI API key is not set")
        return OpenAI(api_key=api_key)

    async def load_resource(self, rag_doc_id: str):
        """Load the resource from DataHub and prepare for chat"""
        if not await self.check_authentication():
            return

        try:

            self.current_doc_id = rag_doc_id

            # Try to load the resource using document_id first
            rag_resource = None
            try:
                rag_resource = RagResource.from_document_id(rag_doc_id)
            except:
                # If that fails, try to load from resource id
                rag_resource = RagResource.from_resource_model_id(rag_doc_id)

            if not rag_resource:
                raise ValueError(f"Resource with ID {rag_doc_id} not found")

            if not rag_resource.is_compatible_with_rag():
                raise ValueError("Resource is not compatible with RAG")

            self._current_rag_resource = rag_resource

            self.subtitle = rag_resource.resource_model.name

        except FileNotFoundError as e:
            Logger.log_exception_stack_trace(e)
            error_message = self.create_text_message(
                content=f"Document not found: {str(e)}",
                role="assistant"
            )

            self.add_message(error_message)
        except ValueError as e:
            Logger.log_exception_stack_trace(e)
            error_message = self.create_text_message(
                content=f"Error loading document: {str(e)}",
                role="assistant"
            )

            self.add_message(error_message)
        except Exception as e:
            Logger.log_exception_stack_trace(e)
            error_message = self.create_text_message(
                content=f"Unexpected error: {str(e)}",
                role="assistant"
            )

            self.add_message(error_message)

    async def call_ai_chat(self, user_message: str):
        """Get streaming response from OpenAI about the document"""

        client = self._get_openai_client()

        uploaded_file_id = await self.upload_file_to_openai()

        async with self:
            # must be used within async with self, becaue it uses selg.get_state
            expert_config = await self._get_config()
        system_prompt = expert_config.system_prompt.replace(expert_config.prompt_file_id_placeholder, uploaded_file_id)

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

    async def handle_output_text_delta(self, event):
        """Handle response.output_text.delta event"""
        text = event.delta

        current_message: Optional[ChatMessage] = None

        async with self:
            current_message = self._current_response_message

        if current_message and current_message.type == "text":
            async with self:
                current_message.content += text
        else:
            # Create new text message if none exists or if current is different type
            new_message = self.create_text_message(
                content=text,
                role="assistant"
            )
            await self.update_current_response_message(new_message)

    async def handle_code_interpreter_call_code_delta(self, event):
        """Handle response.code_interpreter_call_code.delta event"""
        code = event.delta

        current_message: Optional[ChatMessage] = None

        async with self:
            current_message = self._current_response_message

        if current_message and current_message.type == "code":
            async with self:
                current_message.content += code
        else:
            # Create new code message if none exists or if current is different type
            new_message = self.create_code_message(
                content=code,
                role="assistant"
            )
            await self.update_current_response_message(new_message)

    async def handle_output_text_annotation_added(self, event):
        """Handle response.output_text_annotation.added event"""
        annotation = event.annotation

        # Extract file from annotation
        if isinstance(annotation, dict) and 'file_id' in annotation and 'filename' in annotation:
            try:
                client = self._get_openai_client()
                file_message = await self.extract_file_from_response(
                    annotation['file_id'], annotation['filename'], client,
                    container_id=annotation.get('container_id'))
                await self.update_current_response_message(file_message)

            except (OSError, ValueError) as e:
                Logger.log_exception_stack_trace(e)
                # Create error message if image loading fails
                error_message = self.create_text_message(
                    content=f"[Error loading image: {str(e)}]",
                    role="assistant"
                )
                await self.update_current_response_message(error_message)
            except Exception as e:
                Logger.log_exception_stack_trace(e)
                # Create error message for unexpected errors
                error_message = self.create_text_message(
                    content=f"[Unexpected error loading image: {str(e)}]",
                    role="assistant"
                )
                await self.update_current_response_message(error_message)

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

    async def extract_file_from_response(
            self, file_id: str, filename: str, client: OpenAI, container_id: str = None) -> Union[ChatMessageImage, ChatMessageText]:
        """Extract file from OpenAI response - handles images and other files"""

        file_data_binary = None
        try:
            if file_id.startswith('cfile_') and container_id:
                # Container file - use containers API
                file_data_binary = client.containers.files.content.retrieve(file_id, container_id=container_id)
            else:
                # Regular file - use files API
                file_data_binary = client.files.content(file_id)

            # Check file extension to determine handling
            file_extension = os.path.splitext(filename)[1].lower()

            # Handle image files
            if file_extension in ['.png', '.jpg', '.jpeg', '.gif', '.bmp', '.webp']:
                image_data = Image.open(io.BytesIO(file_data_binary.content))
                return self.create_image_message(
                    data=image_data,
                    content="",  # No text content for pure images
                    role="assistant"
                )
            else:
                # Handle other file types as text messages
                return self.create_text_message(
                    content=f"📄 File '{filename}' has been generated.",
                    role="assistant"
                )

        except Exception as e:
            Logger.log_exception_stack_trace(e)
            raise ValueError(f"Error downloading file {file_id}: {str(e)}")

    @rx.var
    async def system_prompt(self) -> str:
        """Get the system prompt for the AI expert"""
        expert_config = await self._get_config()
        return expert_config.system_prompt

    @rx.var
    def document_name(self) -> str:
        """Get the document name for the AI Expert"""
        if self._current_rag_resource:
            return self._current_rag_resource.resource_model.name
        return ''

    @rx.var
    def get_resource_id(self) -> str:
        """Get the resource ID for the AI Expert"""
        if self._current_rag_resource:
            return self._current_rag_resource.get_id()
        return ''

    @rx.event
    def open_current_resource_doc(self):
        """Open the current resource document."""
        if self._current_rag_resource:
            return self.open_document_from_resource(self._current_rag_resource.get_id())
        return None

    async def _get_config(self) -> AiExpertConfig:
        app_config_state = await self.get_state(AppConfigState)
        return await app_config_state.get_config_section('ai_expert_page', AiExpertConfig)

    @rx.var
    async def prompt_file_id_placeholder_readonly(self) -> str:
        """Get the prompt file ID placeholder for readonly display"""
        expert_config = await self._get_config()
        return expert_config.prompt_file_id_placeholder

    @rx.event
    async def handle_config_form_submit(self, form_data: dict):
        """Handle the configuration form submission"""
        try:
            # Get the new system prompt from form data
            new_system_prompt = form_data.get('system_prompt', '').strip()

            if not new_system_prompt:
                return

            # Get current config
            current_config = await self._get_config()

            # Create new config with updated system prompt
            new_config = AiExpertConfig(
                prompt_file_id_placeholder=current_config.prompt_file_id_placeholder,
                system_prompt=new_system_prompt
            )

            # Update the config in AppConfigState
            app_config_state = await self.get_state(AppConfigState)
            return await app_config_state.update_config_section('ai_expert_page', new_config)

        except (ValueError, KeyError) as e:
            Logger.log_exception_stack_trace(e)
            return rx.toast.error(f"Configuration error: {e}")
        except Exception as e:
            Logger.log_exception_stack_trace(e)
            return rx.toast.error(f"Unexpected error updating config: {e}")
