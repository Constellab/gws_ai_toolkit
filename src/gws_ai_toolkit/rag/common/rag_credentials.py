"""Typed credentials for the RAG providers (Dify and RagFlow).

Both providers are reached the same way: a base ``route`` (the API root URL) and an
``api_key``. Historically these were stored as generic key/value credentials
(``CredentialsDataOther``) and read by string keys, which gave no typing and no way
for the credentials picker to distinguish a Dify credential from a RagFlow one.

:class:`CredentialsDataRag` is the shared (unregistered) base that holds the common
``route`` + ``api_key`` fields; it is used by the provider-agnostic layer
(``BaseRagService``, ``RagServiceFactory``) as a common type. Each provider then has
its own registered credentials type (``gws_ai_toolkit.dify`` and
``gws_ai_toolkit.ragflow``) so a :class:`CredentialsParam` only offers the credentials
that match the task's provider, even though the two share the same fields.
"""

from gws_core import (
    ConfigSpecs,
    CredentialsDataBase,
    StrParam,
    credentials_type,
)


class CredentialsDataRag(CredentialsDataBase):
    """Common shape for RAG provider credentials: API root URL and API key.

    This base is intentionally not decorated with ``@credentials_type``: it is never
    stored or selected directly, it only serves as a common type for the provider-agnostic
    RAG layer. Concrete, registered types are :class:`CredentialsDataDify` and
    :class:`CredentialsDataRagflow`.
    """

    # API root URL of the RAG instance (e.g. "https://api.dify.ai/v1").
    route: str
    # API key used to authenticate the requests.
    api_key: str

    @classmethod
    def _rag_specs(cls, instance_name: str) -> ConfigSpecs:
        """Build the shared specs, parameterized by the provider name for the descriptions."""
        return ConfigSpecs(
            {
                "route": StrParam(
                    human_name="Route",
                    short_description=f"API root URL of the {instance_name} instance",
                ),
                "api_key": StrParam(human_name="API key"),
            }
        )


@credentials_type(
    "dify",
    human_name="Dify",
    short_description="Dify API credentials (route + api_key)",
)
class CredentialsDataDify(CredentialsDataRag):
    """Format of the data for Dify credentials."""

    @classmethod
    def get_specs(cls) -> ConfigSpecs:
        return cls._rag_specs("Dify")


@credentials_type(
    "ragflow",
    human_name="RagFlow",
    short_description="RagFlow API credentials (route + api_key)",
)
class CredentialsDataRagflow(CredentialsDataRag):
    """Format of the data for RagFlow credentials."""

    @classmethod
    def get_specs(cls) -> ConfigSpecs:
        return cls._rag_specs("RagFlow")
