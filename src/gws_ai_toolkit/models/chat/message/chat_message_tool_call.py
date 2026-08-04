from typing import TYPE_CHECKING, Literal

from gws_ai_toolkit.models.chat.message.chat_message_base import ChatMessageBase

if TYPE_CHECKING:
    from gws_ai_toolkit.models.chat.chat_conversation import ChatConversation
    from gws_ai_toolkit.models.chat.chat_message_model import ChatMessageModel


@ChatMessageBase.register_message_type
class ChatMessageToolCall(ChatMessageBase):
    """Persisted counterpart of a pydantic-ai ``ToolCallPart``.

    **History-only: this message is never rendered.** It exists so a restored conversation can
    show the model what it already asked to run. Conversation history is client-side (a
    ``list[ModelMessage]`` rebuilt on every restore), so the persisted rows *are* what the model
    sees again — a tool call that is not persisted is a tool call the model forgets, and it will
    happily call the same tool a second time.

    The payload rides in ``ChatMessageModel.data`` rather than ``.message`` because it is
    structured (name, arguments, correlation id) rather than prose. No schema change is needed:
    ``type`` is a ``CharField(20)`` and ``"tool_call"`` fits, ``data`` is already a ``JSONField``.

    ``role`` is ``"assistant"`` because pydantic-ai carries tool calls on the model *response*.

    Attributes:
        message_type: Fixed as "tool_call".
        role: Fixed as "assistant".
        tool_name: Name of the tool the model asked to run.
        args: Arguments the model passed, as a JSON-serialisable dict.
        tool_call_id: Provider-side correlation id, pairing this call with its
            :class:`ChatMessageToolResult`.

    Example:
        call = ChatMessageToolCall(
            tool_name="search_knowledge_base",
            args={"query": "annual report"},
            tool_call_id="call_abc123",
        )
    """

    message_type: str = "tool_call"
    role: Literal["assistant"] = "assistant"
    tool_name: str = ""
    args: dict = {}
    tool_call_id: str = ""

    def is_history_only(self) -> bool:
        """A tool call rebuilds the model's history and is never shown to the user.

        :return: Always True
        :rtype: bool
        """
        return True

    def fill_from_model(self, chat_message: "ChatMessageModel") -> None:
        """Fill additional fields from the ChatMessageModel.
        This is called after the initial creation in from_chat_message_model.
        """
        data = chat_message.data or {}
        self.tool_name = data.get("tool_name", "")
        self.args = data.get("args") or {}
        self.tool_call_id = data.get("tool_call_id", "")

    def to_chat_message_model(self, conversation: "ChatConversation") -> "ChatMessageModel":
        """Convert DTO to database ChatMessage model.

        :param conversation: The conversation this message belongs to
        :type conversation: ChatConversation
        :return: ChatMessage database model instance
        :rtype: ChatMessage
        """
        from gws_ai_toolkit.models.chat.chat_message_model import ChatMessageModel

        return ChatMessageModel.build_message(
            conversation=conversation,
            role=self.role,
            type_=self.message_type,
            external_id=self.external_id,
            data={
                "tool_name": self.tool_name,
                "args": self.args,
                "tool_call_id": self.tool_call_id,
            },
        )
