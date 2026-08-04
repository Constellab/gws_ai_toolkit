from unittest import TestCase
from unittest.mock import patch

from gws_ai_toolkit.models.chat.conversation import ai_expert_chat_config
from gws_ai_toolkit.models.chat.conversation.ai_expert_chat_config import (
    AI_EXPERT_CHAT_MODES,
    AiExpertChatConfig,
)
from pydantic import ValidationError


# test_ai_expert_chat_config.py
class TestAiExpertChatConfig(TestCase):
    """Tests for AiExpertChatConfig, in particular the removal of the legacy `full_file` mode."""

    def test_default_mode_is_relevant_chunks(self) -> None:
        config = AiExpertChatConfig()
        self.assertEqual(config.mode, "relevant_chunks")

    def test_selectable_modes(self) -> None:
        self.assertEqual(AI_EXPERT_CHAT_MODES, ["full_text_chunk", "relevant_chunks"])

    def test_surviving_modes_are_accepted(self) -> None:
        for mode in AI_EXPERT_CHAT_MODES:
            config = AiExpertChatConfig(mode=mode)
            self.assertEqual(config.mode, mode)

    def test_legacy_full_file_mode_falls_back_to_relevant_chunks(self) -> None:
        """A persisted config carrying the removed `full_file` mode must load, not raise."""
        config = AiExpertChatConfig(mode="full_file")
        self.assertEqual(config.mode, "relevant_chunks")

    def test_legacy_full_file_mode_from_persisted_json(self) -> None:
        """The fallback must also apply when the config is rebuilt from a stored JSON dict."""
        persisted = {
            "mode": "full_file",
            "model": "gpt-4o",
            "temperature": 0.7,
            "max_chunks": 5,
        }
        config = AiExpertChatConfig(**persisted)
        self.assertEqual(config.mode, "relevant_chunks")
        self.assertEqual(config.model, "gpt-4o")

    def test_legacy_full_file_mode_logs_once(self) -> None:
        """The fallback is announced by a log line, emitted once and not on every config load."""
        with (
            patch.object(AiExpertChatConfig, "removed_mode_warning_logged", False),
            patch.object(ai_expert_chat_config.Logger, "warning") as warning,
        ):
            AiExpertChatConfig(mode="full_file")
            AiExpertChatConfig(mode="full_file")

            warning.assert_called_once()
            self.assertIn("full_file", warning.call_args.args[0])
            self.assertIn("relevant_chunks", warning.call_args.args[0])

    def test_valid_mode_does_not_log(self) -> None:
        with (
            patch.object(AiExpertChatConfig, "removed_mode_warning_logged", False),
            patch.object(ai_expert_chat_config.Logger, "warning") as warning,
        ):
            AiExpertChatConfig(mode="full_text_chunk")

            warning.assert_not_called()

    def test_unknown_mode_still_raises(self) -> None:
        with self.assertRaises(ValidationError):
            AiExpertChatConfig(mode="not_a_mode")
