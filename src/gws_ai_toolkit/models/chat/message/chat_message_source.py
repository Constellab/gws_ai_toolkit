import os
import re
from typing import TYPE_CHECKING, Literal

from gws_core import BaseModelDTO

from gws_ai_toolkit.models.chat.message.chat_message_base import ChatMessageBase
from gws_ai_toolkit.rag.common.rag_models import RagChatSource

if TYPE_CHECKING:
    from gws_ai_toolkit.models.chat.chat_conversation import ChatConversation
    from gws_ai_toolkit.models.chat.chat_message_model import ChatMessageModel


class RagChatSourceFront(BaseModelDTO):
    id: str
    document_id: str
    document_name: str
    document_extension: str = ""


class ChatMessageSource(ChatMessageBase):
    """Chat message containing text content from assistant.

    Specialized chat message for text-based content, ensuring proper typing
    and validation for text messages. This is the most common message type
    in chat conversations.

    Attributes:
        type: Fixed as "text" to identify this as a text message
        content (str): The text content of the message

    Example:
        text_msg = ChatMessageText(
            role="assistant",
            content="Here is the answer to your question.",
            id="msg_text_123"
        )
    """

    type: Literal["source"] = "source"
    role: Literal["assistant"] = "assistant"
    content: str = ""
    sources: list[RagChatSource] | None = None

    @classmethod
    def create_with_updated_source_ids(
        cls,
        content: str,
        sources: list[RagChatSource] | None = None,
        external_id: str | None = None,
    ) -> "ChatMessageSource":
        """Create a ChatMessageSource and update source ID references in content.

        Factory method that creates a ChatMessageSource instance and automatically
        updates [ID:X] patterns in the content to use actual source IDs.

        Args:
            content: The message content with [ID:X] patterns to be replaced
            sources: List of RagChatSource objects
            external_id: Optional external identifier for the message
            **kwargs: Additional keyword arguments passed to the constructor

        Returns:
            ChatMessageSource: A new instance with updated source ID references

        Example:
            message = ChatMessageSource.create_with_updated_source_ids(
                content="See [ID:0] and [ID:1]",
                sources=[source1, source2]
            )
        """

        instance = cls(
            content=content,
            sources=sources,
            external_id=external_id,
        )
        instance.update_sources_ids_in_content()
        return instance

    def update_sources_ids_in_content(self) -> None:
        """Update source ID references in content from indices to actual source IDs.

        Replaces [ID:X] patterns where X is an index with [ID:source.id] using the
        actual source ID from the sources list. If the index doesn't exist in the
        sources list, removes the [ID:X] pattern entirely.
        """
        if not self.content or not self.sources:
            return

        def replace_source_id(match: re.Match) -> str:
            index = int(match.group(1))
            # Check if the index is valid
            if 0 <= index < len(self.sources):
                # Replace with the actual source ID
                return f"[ID:{self.sources[index].id}]"
            else:
                # Remove invalid references
                return ""

        # Find and replace all [ID:X] patterns
        self.content = re.sub(r"\[ID:(\d+)\]", replace_source_id, self.content)

    def get_source_by_id(self, source_id: str) -> RagChatSource | None:
        """Find and return a source by its ID.

        Args:
            source_id: The ID of the source to find

        Returns:
            RagChatSource | None: The source if found, None otherwise
        """
        if not self.sources:
            return None
        return next((s for s in self.sources if s.id == source_id), None)

    def fill_from_model(self, chat_message: "ChatMessageModel") -> None:
        """Fill additional fields from the ChatMessageModel.
        This is called after the initial creation in from_chat_message_model.
        """
        self.content = chat_message.message or ""
        self.sources = (
            [source.to_rag_dto() for source in chat_message.sources] if chat_message.sources else []
        )

    def _format_content_as_markdown(self) -> str:
        """Format content as markdown with inline source placeholders.

        Replaces [ID:X] patterns with HTML spans that will be styled as source buttons.

        Returns:
            str: Markdown-formatted content with embedded source placeholder spans
        """
        if not self.content:
            return ""

        def replace_source_id(match: re.Match) -> str:
            source_id = match.group(1)
            return f"<span class='source-placeholder' data-source-id='{source_id}'>i</span>"

        # Replace all [ID:X] patterns with source placeholder spans
        return re.sub(r"\[ID:([^\]]+)\]", replace_source_id, self.content)

    def to_front_dto(self) -> "ChatMessageSourceFront":
        """Convert to lightweight front-end DTO with markdown content.

        Returns:
            ChatMessageSourceFront: Frontend message with markdown content
        """
        # Make sources unique by document_id, keeping the highest score
        unique_sources: dict[str, RagChatSourceFront] = {}
        for s in self.sources or []:
            if s.document_id not in unique_sources:
                _, ext = os.path.splitext(s.document_name)
                extension = ext.lstrip(".").upper() if ext else ""
                unique_sources[s.document_id] = RagChatSourceFront(
                    id=s.id,
                    document_id=s.document_id,
                    document_name=s.document_name,
                    document_extension=extension,
                )

        return ChatMessageSourceFront(
            id=self.id,
            content=self._format_content_as_markdown(),
            external_id=self.external_id,
            sources=list(unique_sources.values()),
        )

    def to_chat_message_model(self, conversation: "ChatConversation") -> "ChatMessageModel":
        """Convert DTO to database ChatMessage model.

        :param conversation: The conversation this message belongs to
        :type conversation: ChatConversation
        :return: ChatMessage database model instance
        :rtype: ChatMessage
        """
        # Import at runtime to avoid circular imports
        # This is necessary since ChatMessage also imports from this module
        from gws_ai_toolkit.models.chat.chat_message_model import ChatMessageModel

        return ChatMessageModel.build_message(
            conversation=conversation,
            role=self.role,
            type_=self.type,
            content=self.content,
            external_id=self.external_id,
        )


class ChatMessageSourceFront(ChatMessageBase):
    """Lightweight version of ChatMessageSource for front-end rendering.

    Contains markdown-formatted content with embedded source placeholder spans
    that can be styled and made clickable via CSS and JavaScript.

    Attributes:
        type: Fixed as "source" to identify this message type
        role: Fixed as "assistant"
        content: Markdown content with <span class='source-placeholder'> elements
    """

    type: Literal["source"] = "source"
    role: Literal["assistant"] = "assistant"
    content: str = ""
    sources: list[RagChatSourceFront]
