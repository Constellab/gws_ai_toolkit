"""Rebuild a pydantic-ai message history from persisted chat messages.

Conversation history is client-side: the agents carry a ``list[ModelMessage]`` on the instance
across turns and never rely on a provider-side conversation handle. That makes the persisted
``ChatMessageModel`` rows the only record of a conversation — on restore they are what the model
gets to see again. This module owns that translation, so every conversation restores the same way
instead of each re-deriving the mapping.

The reverse direction (recording tool turns as they happen) lives on
:class:`~gws_ai_toolkit.models.chat.conversation.base_chat_conversation.BaseChatConversation`,
because it has to happen *in stream order*, interleaved with the visible messages of the same
turn, and the conversation is what owns that stream.
"""

from collections.abc import Sequence
from typing import Any

from pydantic_ai.messages import (
    ModelMessage,
    ModelRequest,
    ModelRequestPart,
    ModelResponse,
    ModelResponsePart,
    TextPart,
    ToolCallPart,
    ToolReturnPart,
    UserPromptPart,
)

from gws_ai_toolkit.models.chat.message.chat_message_base import ChatMessageBase
from gws_ai_toolkit.models.chat.message.chat_message_source import ChatMessageSource
from gws_ai_toolkit.models.chat.message.chat_message_text import ChatMessageText
from gws_ai_toolkit.models.chat.message.chat_message_tool_call import ChatMessageToolCall
from gws_ai_toolkit.models.chat.message.chat_message_tool_result import ChatMessageToolResult
from gws_ai_toolkit.models.chat.message.chat_user_message import ChatUserMessageBase

# A history part together with the side of the exchange it belongs to. True means the request
# (user) side, False the response (assistant) side.
_SidedPart = tuple[bool, ModelRequestPart | ModelResponsePart]


class ChatMessageHistoryMapper:
    """Maps persisted chat messages onto a pydantic-ai message history."""

    @classmethod
    def to_model_messages(cls, messages: Sequence[ChatMessageBase]) -> list[ModelMessage]:
        """Rebuild a pydantic-ai message history from persisted chat messages.

        The messages must be in creation order — which is what
        ``ChatConversationService.get_messages_of_conversation`` returns — because the order of
        the produced history is the order in which the model relives the conversation.

        Mapping::

            ChatUserMessageBase (user prose)     -> UserPromptPart   on a ModelRequest
            ChatMessageText / ChatMessageSource  -> TextPart         on a ModelResponse
            ChatMessageToolCall                  -> ToolCallPart     on a ModelResponse
            ChatMessageToolResult                -> ToolReturnPart   on a ModelRequest

        Consecutive parts on the same side are merged into a single message, because that is the
        shape pydantic-ai itself produces: an assistant ``TextPart`` followed by a ``ToolCallPart``
        is one ``ModelResponse``, not two.

        Every other message type is skipped, and skipping them is correct rather than lossy:

        * ``error`` / ``hint`` are messages this application writes *to the user about itself*;
          the model never produced or received them.
        * ``streaming-text`` is the transient partial of a response whose final text is persisted
          as its own ``text`` message — replaying it would duplicate the answer.
        * ``code`` / ``image`` / ``plotly`` / ``table`` are renderings of what a tool produced.
          What the *model* was told about that work is the paired ``tool_result``, which is
          replayed; the artefacts themselves were never in the model's context.

        A tool call whose result was not persisted (and vice-versa) is dropped too: a run
        interrupted between the two rows would otherwise restore with an unpaired tool call, which
        providers reject — making the conversation unusable rather than merely incomplete.

        :param messages: Persisted chat messages, oldest first
        :type messages: Sequence[ChatMessageBase]
        :return: The message history to hand to the next agent run
        :rtype: list[ModelMessage]
        """
        paired_tool_call_ids = cls._paired_tool_call_ids(messages)

        sided_parts: list[_SidedPart] = []
        for message in messages:
            sided_part = cls._to_sided_part(message, paired_tool_call_ids)
            if sided_part is not None:
                sided_parts.append(sided_part)

        return cls._merge_sided_parts(sided_parts)

    @classmethod
    def _to_sided_part(
        cls, message: ChatMessageBase, paired_tool_call_ids: set[str]
    ) -> _SidedPart | None:
        """Convert one persisted message to a history part, or None when the model never saw it.

        :param message: The persisted message to convert
        :type message: ChatMessageBase
        :param paired_tool_call_ids: Tool call ids whose call and result were both persisted;
            any other tool turn is dropped
        :type paired_tool_call_ids: set[str]
        :return: The part and the side of the exchange it belongs to, or None to skip the message
        :rtype: _SidedPart | None
        """
        if isinstance(message, ChatMessageToolCall):
            if message.tool_call_id not in paired_tool_call_ids:
                return None
            return (
                False,
                ToolCallPart(
                    tool_name=message.tool_name,
                    args=message.args,
                    tool_call_id=message.tool_call_id,
                ),
            )

        if isinstance(message, ChatMessageToolResult):
            if message.tool_call_id not in paired_tool_call_ids:
                return None
            return (
                True,
                ToolReturnPart(
                    tool_name=message.tool_name,
                    content=message.content,
                    tool_call_id=message.tool_call_id,
                ),
            )

        if isinstance(message, ChatUserMessageBase):
            # Covers the text and the table-bearing user messages: only the prompt text was ever
            # in the model's context. Tables reach it through the run's instructions and
            # dependencies, which are rebuilt per run rather than persisted.
            return (True, UserPromptPart(content=message.content)) if message.content else None

        if isinstance(message, (ChatMessageText, ChatMessageSource)):
            return (False, TextPart(content=message.content)) if message.content else None

        return None

    @classmethod
    def _paired_tool_call_ids(cls, messages: Sequence[ChatMessageBase]) -> set[str]:
        """Collect the tool call ids having both a persisted call and a persisted result.

        :param messages: Persisted chat messages
        :type messages: Sequence[ChatMessageBase]
        :return: The tool call ids that can safely be replayed
        :rtype: set[str]
        """
        call_ids = {
            message.tool_call_id
            for message in messages
            if isinstance(message, ChatMessageToolCall) and message.tool_call_id
        }
        result_ids = {
            message.tool_call_id
            for message in messages
            if isinstance(message, ChatMessageToolResult) and message.tool_call_id
        }
        return call_ids & result_ids

    @classmethod
    def _merge_sided_parts(cls, sided_parts: Sequence[_SidedPart]) -> list[ModelMessage]:
        """Group consecutive parts of the same side into one message each.

        :param sided_parts: Parts in conversation order, each tagged with its side
        :type sided_parts: Sequence[_SidedPart]
        :return: The message history, alternating requests and responses
        :rtype: list[ModelMessage]
        """
        history: list[ModelMessage] = []
        current_side: bool | None = None
        current_parts: list[Any] = []

        for is_request, part in sided_parts:
            if current_side is not None and is_request != current_side:
                history.append(cls._build_message(current_side, current_parts))
                current_parts = []
            current_side = is_request
            current_parts.append(part)

        if current_side is not None and current_parts:
            history.append(cls._build_message(current_side, current_parts))

        return history

    @staticmethod
    def _build_message(is_request: bool, parts: list[Any]) -> ModelMessage:
        """Wrap parts into the message of the matching side.

        :param is_request: True for the request (user) side, False for the response side
        :type is_request: bool
        :param parts: The parts of the message
        :type parts: list[Any]
        :return: The pydantic-ai message
        :rtype: ModelMessage
        """
        if is_request:
            return ModelRequest(parts=parts)
        return ModelResponse(parts=parts)
