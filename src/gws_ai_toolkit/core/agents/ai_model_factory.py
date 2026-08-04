"""Factory turning ``provider:model`` configuration strings into pydantic-ai models.

Every configuration surface in this brick names its model as a ``provider:model`` string
(``openai:gpt-4o``, ``anthropic:claude-opus-4-6``, ...) so that switching provider is a
configuration change rather than a code change. This module is the single place where a
provider-specific client is constructed; keeping it here means the agents themselves stay
provider agnostic.
"""

from gws_core import Logger
from pydantic_ai.models import Model, infer_model
from pydantic_ai.models.openai import OpenAIResponsesModel
from pydantic_ai.providers.openai import OpenAIProvider

DEFAULT_PROVIDER = "openai"


class AiModelFactory:
    """Builds pydantic-ai ``Model`` instances from ``provider:model`` strings."""

    @classmethod
    def build(cls, model: str | Model, api_key: str | None = None) -> Model:
        """Build a pydantic-ai model from a ``provider:model`` string.

        Args:
            model: Either a ``provider:model`` string, or an already built pydantic-ai
                ``Model``. Passing a ``Model`` through untouched is what lets tests inject
                ``TestModel`` / ``FunctionModel`` without any API call.
            api_key: Optional API key for the provider. When omitted, the provider falls
                back to its usual environment variable (``OPENAI_API_KEY`` and friends).

        Returns:
            The pydantic-ai model to hand to an ``Agent``.

        Raises:
            ValueError: If the model string is empty.
        """
        if isinstance(model, Model):
            return model

        provider, model_name = cls.split_model_spec(model)

        if provider == DEFAULT_PROVIDER and api_key:
            # Only the OpenAI branch takes an explicit key today: it is the sole provider
            # exercised so far, and the other agents read their key from the environment.
            return OpenAIResponsesModel(model_name, provider=OpenAIProvider(api_key=api_key))

        return infer_model(f"{provider}:{model_name}")

    @classmethod
    def split_model_spec(cls, model: str) -> tuple[str, str]:
        """Split a ``provider:model`` string into its provider and model name.

        A bare model name (no ``provider:`` prefix) is read as an OpenAI model and logged,
        so that configurations persisted before the pydantic-ai migration keep loading
        instead of raising.

        Args:
            model: The configured model string.

        Returns:
            Tuple of (provider, model_name).

        Raises:
            ValueError: If the model string is empty.
        """
        if not model or not model.strip():
            raise ValueError("No model configured. Expected a 'provider:model' string.")

        model = model.strip()

        if ":" not in model:
            Logger.warning(
                f"Model '{model}' has no 'provider:' prefix. Reading it as "
                f"'{DEFAULT_PROVIDER}:{model}'. Update the configuration to a "
                "'provider:model' string."
            )
            return DEFAULT_PROVIDER, model

        provider, model_name = model.split(":", 1)
        return provider.strip(), model_name.strip()

    @classmethod
    def model_spec(cls, model: str | Model) -> str:
        """Return the ``provider:model`` string for a configured model.

        Used to echo the model back onto conversation metadata, where a string is expected
        even when the agent was built from a ``Model`` instance.

        Args:
            model: A ``provider:model`` string or a pydantic-ai ``Model``.

        Returns:
            The normalised ``provider:model`` string.
        """
        if isinstance(model, Model):
            return f"{model.system}:{model.model_name}"

        provider, model_name = cls.split_model_spec(model)
        return f"{provider}:{model_name}"
