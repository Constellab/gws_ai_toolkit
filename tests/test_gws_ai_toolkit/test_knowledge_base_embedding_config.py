"""The embedding width is derived from the model, not configured.

These tests exist because the width is the one embedding property that corrupts retrieval silently
when it is wrong. Deriving it removes the chance to mistype it — but derivation is only safe if an
unknown model *refuses* rather than guesses, and if an explicitly-chosen (truncated) width still
wins. Both are asserted here.
"""

from gws_ai_toolkit.rag.knowledge_base.knowledge_base_config import (
    DEFAULT_OPENAI_EMBEDDING_MODEL,
    EMBEDDING_NATIVE_DIMENSIONS,
    MOCK_EMBEDDING_MODEL,
    EmbeddingConfig,
    EmbeddingProvider,
)
from gws_core import BaseTestCase


class TestKnowledgeBaseEmbeddingConfig(BaseTestCase):
    """How ``EmbeddingConfig`` resolves its vector width."""

    def test_the_default_configuration_takes_its_model_native_width(self):
        config = EmbeddingConfig()

        self.assertEqual(config.model, DEFAULT_OPENAI_EMBEDDING_MODEL)
        self.assertEqual(config.dimensions, EMBEDDING_NATIVE_DIMENSIONS[config.model])

    def test_every_known_model_resolves_to_its_own_width(self):
        """Named models must not collapse onto one default — that would be the silent corruption."""
        for model, expected_dimensions in EMBEDDING_NATIVE_DIMENSIONS.items():
            with self.subTest(model=model):
                config = EmbeddingConfig(model=model)
                self.assertEqual(config.dimensions, expected_dimensions)

    def test_the_two_v3_models_do_not_share_a_width(self):
        """A regression guard: the whole point of deriving is that the two differ."""
        small = EmbeddingConfig(model="text-embedding-3-small")
        large = EmbeddingConfig(model="text-embedding-3-large")

        self.assertNotEqual(small.dimensions, large.dimensions)

    def test_the_mock_resolves_without_being_told_its_width(self):
        self.assertEqual(
            EmbeddingConfig.mock().dimensions, EMBEDDING_NATIVE_DIMENSIONS[MOCK_EMBEDDING_MODEL]
        )

    def test_an_explicit_width_wins_over_the_model_native_one(self):
        """Truncation stays possible: it is what the manifest tests rely on."""
        truncated = EmbeddingConfig(model="text-embedding-3-large", dimensions=64)

        self.assertEqual(truncated.dimensions, 64)
        self.assertNotEqual(truncated.dimensions, EMBEDDING_NATIVE_DIMENSIONS[truncated.model])

    def test_the_mock_accepts_an_explicit_width(self):
        self.assertEqual(EmbeddingConfig.mock(dimensions=128).dimensions, 128)

    def test_an_unknown_model_refuses_rather_than_guessing(self):
        """Indexing at a guessed width under a real model's name is what the manifest cannot catch."""
        with self.assertRaises(ValueError) as context:
            EmbeddingConfig(provider=EmbeddingProvider.OPENAI, model="text-embedding-4-imaginary")

        message = str(context.exception)
        self.assertIn("text-embedding-4-imaginary", message)
        # The message must name a way out, not only the problem.
        self.assertIn("dimensions", message)

    def test_an_unknown_model_is_accepted_when_a_width_is_given(self):
        """The escape hatch for a newly released model, before the map knows about it."""
        config = EmbeddingConfig(model="text-embedding-4-imaginary", dimensions=2048)

        self.assertEqual(config.dimensions, 2048)
