"""Resolving the API key the embedding provider needs.

Kept out of :mod:`embedding_factory` so the factory stays a pure mapping from configuration to
embedding, and so tests can build an :class:`~.knowledge_base_config.EmbeddingConfig` without
touching the credentials store.
"""

from gws_core import CredentialsDataOther, CredentialsService, Settings

# Keys accepted inside an "other" credentials entry, in the order they are looked up.
API_KEY_ENTRY_NAMES = ["api_key", "openai_api_key", "key"]


def resolve_openai_api_key(credentials_name: str | None = None) -> str:
    """Return the OpenAI API key to embed with.

    A named credentials entry wins; without one the lab-wide ``OPENAI_API_KEY`` is used, which is
    what the rest of the brick already relies on.

    :param credentials_name: name of an "other" credentials entry holding the key
    :raises ValueError: if the named credentials do not exist, are of the wrong type, or hold no
                        recognised key entry
    """
    if credentials_name:
        credentials = CredentialsService.find_by_name(credentials_name)
        if credentials is None:
            raise ValueError(f"Credentials '{credentials_name}' not found")

        data = credentials.get_data_object()
        if not isinstance(data, CredentialsDataOther):
            raise ValueError(
                f"Credentials '{credentials_name}' must be of type 'other' (key / value pairs)"
            )

        for entry_name in API_KEY_ENTRY_NAMES:
            api_key = data.data.get(entry_name)
            if api_key:
                return api_key

        accepted = ", ".join(API_KEY_ENTRY_NAMES)
        raise ValueError(
            f"Credentials '{credentials_name}' hold no API key. Expected one of: {accepted}."
        )

    return Settings.get_open_ai_api_key()
