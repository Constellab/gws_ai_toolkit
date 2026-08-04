"""Tool turns survive a reload and rebuild the model's message history.

Conversation history is client-side, so the persisted rows *are* what the model sees when a
conversation is restored. These tests cover the two new message types, the mapping back to a
pydantic-ai ``message_history``, and the rule that neither type is ever shown to the user.
"""

import pandas as pd
from gws_ai_toolkit.core.agents.table.table_agent_ai import TableAgentAi
from gws_ai_toolkit.models.chat.chat_app import ChatApp
from gws_ai_toolkit.models.chat.chat_conversation import ChatConversation
from gws_ai_toolkit.models.chat.chat_conversation_dto import SaveChatConversationDTO
from gws_ai_toolkit.models.chat.chat_conversation_service import ChatConversationService
from gws_ai_toolkit.models.chat.chat_message_model import ChatMessageModel
from gws_ai_toolkit.models.chat.conversation.ai_table_agent_chat_conversation import (
    AiTableAgentChatConversation,
)
from gws_ai_toolkit.models.chat.conversation.base_chat_conversation import (
    BaseChatConversationConfig,
)
from gws_ai_toolkit.models.chat.conversation.chat_message_history_mapper import (
    ChatMessageHistoryMapper,
)
from gws_ai_toolkit.models.chat.message.chat_message_base import ChatMessageBase
from gws_ai_toolkit.models.chat.message.chat_message_error import ChatMessageError
from gws_ai_toolkit.models.chat.message.chat_message_text import ChatMessageText
from gws_ai_toolkit.models.chat.message.chat_message_tool_call import ChatMessageToolCall
from gws_ai_toolkit.models.chat.message.chat_message_tool_result import ChatMessageToolResult
from gws_ai_toolkit.models.chat.message.chat_user_message import ChatUserMessageText
from gws_ai_toolkit.models.chat.message.chat_user_message_table import ChatUserMessageTable
from gws_ai_toolkit.models.user.user_sync_service import AiToolkitUserSyncService
from gws_core import BaseTestCase, Table
from pydantic_ai.messages import (
    ModelRequest,
    ModelResponse,
    TextPart,
    ToolCallPart,
    ToolReturnPart,
    UserPromptPart,
)

from .agent_test_helper import ORCHESTRATOR, TRANSFORM, ScriptedModel, ToolCall

RENAME_CODE = "transformed_df = df.rename(columns={'hello': 'x_values'})"


# test_tool_turn_persistence
class TestToolTurnPersistence(BaseTestCase):
    """Persistence and restore of ``tool_call`` / ``tool_result`` message rows."""

    test_chat_app: ChatApp
    service: ChatConversationService

    @classmethod
    def init_before_test(cls):
        super().init_before_test()
        AiToolkitUserSyncService().sync_all_users()
        cls.service = ChatConversationService()

        cls.test_chat_app = ChatApp()
        cls.test_chat_app.name = "test_tool_turns"
        cls.test_chat_app.save()

    def _save_conversation(self, messages: list[ChatMessageBase]) -> ChatConversation:
        """Persist a conversation made of the given messages, in the given order."""
        return self.service.save_conversation(
            SaveChatConversationDTO(
                chat_app_name=self.test_chat_app.name,
                configuration={},
                mode="knowledge_base",
                label="Tool turns",
                messages=messages,
            )
        )

    def _build_table_conversation(
        self, script: dict
    ) -> tuple[AiTableAgentChatConversation, TableAgentAi]:
        """Build a table conversation driven by a scripted model, with no database writes."""
        table_agent = TableAgentAi(
            openai_api_key=None, model=ScriptedModel(script=script).build(), temperature=0.1
        )
        conversation = AiTableAgentChatConversation(
            config=BaseChatConversationConfig("test_tool_turns", store_conversation_in_db=False),
            table_agent=table_agent,
        )
        return conversation, table_agent

    def test_tool_turns_are_persisted_under_the_two_new_types(self):
        """Both rows land in the existing table, with no schema change."""
        conversation = self._save_conversation(
            [
                ChatUserMessageText(content="What does the report say?"),
                ChatMessageToolCall(
                    tool_name="search_knowledge_base",
                    args={"query": "report"},
                    tool_call_id="call_1",
                ),
                ChatMessageToolResult(
                    tool_name="search_knowledge_base",
                    content="chunk 1\nchunk 2",
                    tool_call_id="call_1",
                ),
            ]
        )

        rows = ChatMessageModel.get_by_conversation(str(conversation.id))
        self.assertEqual([row.type for row in rows], ["user-text", "tool_call", "tool_result"])

        call_row = rows[1]
        self.assertEqual(call_row.role, "assistant")
        self.assertEqual(call_row.data["tool_name"], "search_knowledge_base")
        self.assertEqual(call_row.data["args"], {"query": "report"})
        self.assertEqual(call_row.data["tool_call_id"], "call_1")

        result_row = rows[2]
        self.assertEqual(result_row.role, "user")
        self.assertEqual(result_row.data["tool_name"], "search_knowledge_base")
        self.assertEqual(result_row.data["content"], "chunk 1\nchunk 2")
        self.assertEqual(result_row.data["tool_call_id"], "call_1")

        conversation.delete_instance()

    def test_restored_history_contains_the_call_and_its_result(self):
        """A restored conversation shows the model what it already retrieved."""
        conversation = self._save_conversation(
            [
                ChatUserMessageText(content="What does the report say?"),
                ChatMessageToolCall(
                    tool_name="search_knowledge_base",
                    args={"query": "report"},
                    tool_call_id="call_1",
                ),
                ChatMessageToolResult(
                    tool_name="search_knowledge_base",
                    content="chunk 1",
                    tool_call_id="call_1",
                ),
                ChatMessageText(content="The report says X."),
            ]
        )

        messages = self.service.get_messages_of_conversation(str(conversation.id))
        history = ChatMessageHistoryMapper.to_model_messages(messages)

        self.assertEqual(len(history), 4)

        self.assertIsInstance(history[0], ModelRequest)
        self.assertIsInstance(history[0].parts[0], UserPromptPart)
        self.assertEqual(history[0].parts[0].content, "What does the report say?")

        self.assertIsInstance(history[1], ModelResponse)
        call_part = history[1].parts[0]
        self.assertIsInstance(call_part, ToolCallPart)
        self.assertEqual(call_part.tool_name, "search_knowledge_base")
        self.assertEqual(call_part.args_as_dict(), {"query": "report"})
        self.assertEqual(call_part.tool_call_id, "call_1")

        self.assertIsInstance(history[2], ModelRequest)
        return_part = history[2].parts[0]
        self.assertIsInstance(return_part, ToolReturnPart)
        self.assertEqual(return_part.tool_name, "search_knowledge_base")
        self.assertEqual(return_part.content, "chunk 1")
        self.assertEqual(return_part.tool_call_id, "call_1")

        self.assertIsInstance(history[3], ModelResponse)
        self.assertIsInstance(history[3].parts[0], TextPart)
        self.assertEqual(history[3].parts[0].content, "The report says X.")

        conversation.delete_instance()

    def test_tool_turns_are_absent_from_the_visible_transcript(self):
        """The two types are history-only: they are never rendered."""
        conversation = self._save_conversation(
            [
                ChatUserMessageText(content="Question"),
                ChatMessageToolCall(tool_name="tool", args={}, tool_call_id="call_1"),
                ChatMessageToolResult(tool_name="tool", content="result", tool_call_id="call_1"),
                ChatMessageText(content="Answer"),
            ]
        )

        messages = self.service.get_messages_of_conversation(str(conversation.id))

        # Every persisted row is loaded, so the history can be rebuilt from them...
        self.assertEqual(
            [message.message_type for message in messages],
            ["user-text", "tool_call", "tool_result", "text"],
        )
        # ...but only the prose is rendered.
        self.assertEqual(
            [message.message_type for message in ChatMessageBase.filter_visible(messages)],
            ["user-text", "text"],
        )

        conversation.delete_instance()

    def test_error_and_hint_messages_stay_visible(self):
        """Only the tool turn types are history-only; the rest of the transcript is untouched."""
        messages = [
            ChatUserMessageText(content="Question"),
            ChatMessageError(error="Something failed"),
            ChatMessageText(content="Answer"),
        ]

        self.assertEqual(ChatMessageBase.filter_visible(messages), messages)

    def test_sequential_tool_turns_restore_in_order(self):
        """Several tool turns of one conversation keep their order across a reload."""
        conversation = self._save_conversation(
            [
                ChatUserMessageText(content="Compare both reports"),
                ChatMessageToolCall(tool_name="search", args={"query": "a"}, tool_call_id="call_1"),
                ChatMessageToolResult(tool_name="search", content="a chunk", tool_call_id="call_1"),
                ChatMessageToolCall(tool_name="search", args={"query": "b"}, tool_call_id="call_2"),
                ChatMessageToolResult(tool_name="search", content="b chunk", tool_call_id="call_2"),
                ChatMessageText(content="Both reports agree."),
            ]
        )

        messages = self.service.get_messages_of_conversation(str(conversation.id))
        history = ChatMessageHistoryMapper.to_model_messages(messages)

        parts = [part for message in history for part in message.parts]
        self.assertEqual(
            [(type(part).__name__, getattr(part, "tool_call_id", None)) for part in parts],
            [
                ("UserPromptPart", None),
                ("ToolCallPart", "call_1"),
                ("ToolReturnPart", "call_1"),
                ("ToolCallPart", "call_2"),
                ("ToolReturnPart", "call_2"),
                ("TextPart", None),
            ],
        )

        # Each tool turn is its own request/response pair, so the model reads them in sequence.
        self.assertEqual(
            [type(message).__name__ for message in history],
            [
                "ModelRequest",
                "ModelResponse",
                "ModelRequest",
                "ModelResponse",
                "ModelRequest",
                "ModelResponse",
            ],
        )

        conversation.delete_instance()

    def test_messages_of_one_turn_keep_their_order_despite_equal_timestamps(self):
        """`created_at` has second precision, so the saved position is what orders a turn."""
        conversation = self._save_conversation(
            [
                ChatUserMessageText(content="Question"),
                ChatMessageToolCall(tool_name="search", args={}, tool_call_id="call_1"),
                ChatMessageToolResult(tool_name="search", content="chunk", tool_call_id="call_1"),
                ChatMessageText(content="Answer"),
            ]
        )

        rows = ChatMessageModel.get_by_conversation(str(conversation.id))

        # The whole turn was saved within the same second, so ordering cannot rely on created_at.
        self.assertEqual(len({row.created_at for row in rows}), 1)
        self.assertEqual([row.get_sequence() for row in rows], [0, 1, 2, 3])
        self.assertEqual(
            [row.type for row in rows], ["user-text", "tool_call", "tool_result", "text"]
        )

        conversation.delete_instance()

    def test_a_tool_call_without_its_result_is_dropped(self):
        """An interrupted turn must not leave a dangling call in the rebuilt history."""
        conversation = self._save_conversation(
            [
                ChatUserMessageText(content="Question"),
                ChatMessageToolCall(tool_name="search", args={}, tool_call_id="call_1"),
            ]
        )

        messages = self.service.get_messages_of_conversation(str(conversation.id))
        history = ChatMessageHistoryMapper.to_model_messages(messages)

        self.assertEqual(len(history), 1)
        self.assertIsInstance(history[0].parts[0], UserPromptPart)

        conversation.delete_instance()

    def test_a_tool_result_without_its_call_is_dropped(self):
        """The reverse case is dropped too, rather than replayed as an orphan return."""
        conversation = self._save_conversation(
            [
                ChatUserMessageText(content="Question"),
                ChatMessageToolResult(tool_name="search", content="chunk", tool_call_id="call_1"),
                ChatMessageText(content="Answer"),
            ]
        )

        messages = self.service.get_messages_of_conversation(str(conversation.id))
        history = ChatMessageHistoryMapper.to_model_messages(messages)

        self.assertEqual(len(history), 2)
        self.assertIsInstance(history[0].parts[0], UserPromptPart)
        self.assertIsInstance(history[1].parts[0], TextPart)

        conversation.delete_instance()

    def test_a_conversation_records_the_tool_turns_of_its_own_agent(self):
        """The table conversation records its orchestrator's tool turns, not its sub-agents'."""
        conversation, _ = self._build_table_conversation(
            {
                ORCHESTRATOR: [
                    ToolCall(
                        "transform_table",
                        {
                            "table_name": "test_data",
                            "output_table_name": "renamed_data",
                            "user_request": "Rename 'hello' to 'x_values'",
                        },
                    ),
                    "Renamed the column.",
                ],
                TRANSFORM: [
                    ToolCall(
                        "transform_dataframe",
                        {"code": RENAME_CODE, "transformed_table_name": "renamed_data"},
                    )
                ],
            }
        )
        conversation.create_conversation("Rename a column")

        user_message = ChatUserMessageTable(
            content="Rename the column 'hello' to 'x_values'",
            tables={"test_data": Table(pd.DataFrame({"hello": [1], "y_values": [2]}))},
        )
        list(conversation.call_conversation(user_message))

        tool_calls = [
            message
            for message in conversation.chat_messages
            if isinstance(message, ChatMessageToolCall)
        ]
        tool_results = [
            message
            for message in conversation.chat_messages
            if isinstance(message, ChatMessageToolResult)
        ]

        # Only the orchestrator's own turn: the sub-agent's transform_dataframe call belongs to
        # the sub-agent's history, and sub-agents are rebuilt from scratch on the next run.
        self.assertEqual([call.tool_name for call in tool_calls], ["transform_table"])
        self.assertEqual([result.tool_name for result in tool_results], ["transform_table"])
        self.assertEqual(tool_calls[0].tool_call_id, tool_results[0].tool_call_id)
        self.assertEqual(tool_calls[0].args["table_name"], "test_data")

        # The recorded turn comes before the answer it led to, so a restore replays it in order.
        recorded = [message.message_type for message in conversation.chat_messages]
        self.assertLess(recorded.index("tool_call"), recorded.index("tool_result"))
        self.assertLess(recorded.index("tool_result"), recorded.index("text"))

        # None of it is shown to the user.
        visible = [message.message_type for message in conversation.get_visible_messages()]
        self.assertNotIn("tool_call", visible)
        self.assertNotIn("tool_result", visible)

        # And the recorded turn rebuilds into a paired history.
        history = ChatMessageHistoryMapper.to_model_messages(conversation.chat_messages)
        part_types = [type(part).__name__ for message in history for part in message.parts]
        self.assertIn("ToolCallPart", part_types)
        self.assertIn("ToolReturnPart", part_types)

    def test_a_failed_tool_call_is_recorded_with_the_error_the_model_received(self):
        """A tool that failed still pairs, so the retry that followed restores cleanly."""
        conversation, _ = self._build_table_conversation(
            {
                ORCHESTRATOR: [
                    ToolCall(
                        "transform_table",
                        {
                            "table_name": "does_not_exist",
                            "output_table_name": "out",
                            "user_request": "Do something",
                        },
                    ),
                    "I could not find that table.",
                ],
            }
        )
        conversation.create_conversation("Missing table")

        user_message = ChatUserMessageTable(
            content="Transform the missing table",
            tables={"test_data": Table(pd.DataFrame({"a": [1]}))},
        )
        list(conversation.call_conversation(user_message))

        tool_results = [
            message
            for message in conversation.chat_messages
            if isinstance(message, ChatMessageToolResult)
        ]
        self.assertEqual(len(tool_results), 1)
        self.assertIn("does_not_exist", tool_results[0].content)

        # Paired, so the failed call survives the rebuild rather than being dropped.
        history = ChatMessageHistoryMapper.to_model_messages(conversation.chat_messages)
        part_types = [type(part).__name__ for message in history for part in message.parts]
        self.assertIn("ToolCallPart", part_types)
        self.assertIn("ToolReturnPart", part_types)

    def test_restoring_a_conversation_sets_the_agent_message_history(self):
        """Restore hands the rebuilt history to the agent, so the next turn continues it."""
        conversation, table_agent = self._build_table_conversation(
            {ORCHESTRATOR: ["Nothing to do."]}
        )

        conversation.restore_messages(
            [
                ChatUserMessageText(content="Question"),
                ChatMessageToolCall(tool_name="search", args={"q": "x"}, tool_call_id="call_1"),
                ChatMessageToolResult(tool_name="search", content="chunk", tool_call_id="call_1"),
                ChatMessageText(content="Answer"),
            ]
        )

        history = table_agent.get_message_history()
        self.assertEqual(len(history), 4)
        self.assertIsInstance(history[1].parts[0], ToolCallPart)
        self.assertIsInstance(history[2].parts[0], ToolReturnPart)

        # The restored messages are the conversation's messages, tool turns included.
        self.assertEqual(len(conversation.chat_messages), 4)
        self.assertEqual(len(conversation.get_visible_messages()), 2)
