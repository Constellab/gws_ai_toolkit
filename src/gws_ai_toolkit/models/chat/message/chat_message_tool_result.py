from typing import TYPE_CHECKING, Literal

from gws_ai_toolkit.models.chat.message.chat_message_base import ChatMessageBase

if TYPE_CHECKING:
    from gws_ai_toolkit.models.chat.chat_conversation import ChatConversation
    from gws_ai_toolkit.models.chat.chat_message_model import ChatMessageModel


@ChatMessageBase.register_message_type
class ChatMessageToolResult(ChatMessageBase):
    """Persisted counterpart of a pydantic-ai ``ToolReturnPart``.

    **History-only: this message is never rendered.** It is the other half of a
    :class:`~gws_ai_toolkit.models.chat.message.chat_message_tool_call.ChatMessageToolCall`: what
    the tool reported back. Both halves have to survive a reload, because a model shown its own
    call but not the answer re-runs the tool, and because a history carrying an unpaired tool call
    is rejected by the provider.

    The content is what the model was actually told — for a tool that failed, that is the error
    message it was asked to correct. An honest history, not a reconstruction of what should have
    happened.

    Whatever of the tool's work is worth *showing* the user is emitted separately as its own
    renderable message (code, table, plot, text).

    ``role`` is ``"user"`` because pydantic-ai carries tool returns on the following model
    *request*, i.e. on the user side of the exchange.

    Attributes:
        message_type: Fixed as "tool_result".
        role: Fixed as "user".
        tool_name: Name of the tool that ran.
        content: What the tool reported back to the model.
        tool_call_id: Provider-side correlation id, pairing this result with its call.

    Example:
        result = ChatMessageToolResult(
            tool_name="search_knowledge_base",
            content="3 chunks found: ...",
            tool_call_id="call_abc123",
        )
    """

    message_type: str = "tool_result"
    role: Literal["user"] = "user"
    tool_name: str = ""
    content: str = ""
    tool_call_id: str = ""

    def is_history_only(self) -> bool:
        """A tool result rebuilds the model's history and is never shown to the user.

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
        self.content = data.get("content", "")
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
                "content": self.content,
                "tool_call_id": self.tool_call_id,
            },
        )
