from unittest import TestCase

from gws_ai_toolkit.models.chat.conversation.ai_expert_chat_config import AiExpertChatConfig
from pydantic import ValidationError


# test_ai_expert_chat_config.py
class TestAiExpertChatConfig(TestCase):
    """Tests for AiExpertChatConfig, in particular the removal of the legacy `full_file` mode."""

    def test_default_mode_is_relevant_chunks(self):
        config = AiExpertChatConfig()
        self.assertEqual(config.mode, "relevant_chunks")

    def test_surviving_modes_are_accepted(self):
        for mode in ["full_text_chunk", "relevant_chunks"]:
            config = AiExpertChatConfig(mode=mode)
            self.assertEqual(config.mode, mode)

    def test_legacy_full_file_mode_falls_back_to_relevant_chunks(self):
        """A persisted config carrying the removed `full_file` mode must load, not raise."""
        config = AiExpertChatConfig(mode="full_file")
        self.assertEqual(config.mode, "relevant_chunks")

    def test_legacy_full_file_mode_from_persisted_json(self):
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

    def test_unknown_mode_still_raises(self):
        with self.assertRaises(ValidationError):
            AiExpertChatConfig(mode="not_a_mode")
