"""The ``RagChatProfile`` row: a named, user-selectable knowledge-base chat configuration.

**The bound knowledge bases are the retrieval filter.** ``knowledge_base_ids`` is not a convenience
list: it is exactly what a retrieval passes to the engine as its metadata filter, which is why this
one column is where the management layer and the retrieval layer connect.

The binding is a **soft many-to-many**: a JSON list of ids with no foreign key and therefore no
referential integrity. That is a deliberate V1 trade-off (a join table is a follow-up), and it is
paid for on both sides — ids are validated when a profile is saved, and ids whose knowledge base has
since disappeared are dropped at query time rather than raising. See
:class:`~.rag_chat_profile_service.RagChatProfileService`.
"""

from datetime import datetime

from gws_core import JSONField, Model, NullableDateTimeUTC, NullableForeignKeyField
from peewee import BooleanField, CharField, FloatField, IntegerField, ModelSelect, TextField

from gws_ai_toolkit.core.ai_toolkit_db_manager import AiToolkitDbManager
from gws_ai_toolkit.models.knowledge_base.rag_chat_profile_dto import (
    DEFAULT_CHAT_PROFILE_MODEL,
    DEFAULT_CHAT_PROFILE_SYSTEM_PROMPT,
    RagChatProfileDTO,
)
from gws_ai_toolkit.models.user.user import User
from gws_ai_toolkit.rag.knowledge_base.knowledge_base_config import DEFAULT_TOP_K, RetrievalConfig


class RagChatProfile(Model):
    """A chat profile: which knowledge bases to search, how, and with which model and prompt."""

    name: str = CharField(max_length=100, unique=True)
    system_prompt: str = TextField(default=DEFAULT_CHAT_PROFILE_SYSTEM_PROMPT)
    # pydantic-ai ``provider:model`` string, resolved by AiModelFactory.
    model: str = CharField(max_length=100, default=DEFAULT_CHAT_PROFILE_MODEL)
    top_k: int = IntegerField(default=DEFAULT_TOP_K)
    # Defined against the **fused RRF ``_relevance_score``** the engine returns in hybrid mode:
    # rank-derived, roughly 0.015-0.033 in practice, and *not* a cosine similarity. A value carried
    # over from a cosine-tuned configuration (0.5, say) rejects every chunk, so the default is None
    # — "no threshold" — rather than a number that looks reasonable on the wrong scale.
    score_threshold: float | None = FloatField(null=True)
    # Bound knowledge bases: this list *is* the retrieval metadata filter. Soft many-to-many.
    knowledge_base_ids: list[str] = JSONField(default=list)

    # Publication columns for the public chat API (knowledge_base_public_api_plan.md).
    #
    # Publishing mints ``publish_token`` and un-publishing clears it, via
    # :meth:`~.rag_chat_profile_service.RagChatProfileService.publish_profile` /
    # ``unpublish_profile``. The route that authenticates external callers against this token is
    # separate work; here, the token *is* the scope, because V1 has no per-document access
    # filtering — every chunk carries ``access_scope = "*"``.
    #
    # ``publish_token`` is a credential: it must never reach a Reflex state or a log, which is why it
    # is absent from :class:`~.rag_chat_profile_dto.RagChatProfileDTO`. ``published_by`` is not a
    # credential and only records who last published the profile — kept after an un-publish as the
    # record of the last time it was reachable, rather than cleared.
    is_published: bool = BooleanField(default=False)
    publish_token: str | None = CharField(max_length=64, null=True, unique=True, index=True)
    published_at: datetime | None = NullableDateTimeUTC()
    published_by = NullableForeignKeyField(User, backref="+")

    class Meta:
        table_name = "gws_ai_toolkit_rag_chat_profile"
        database = AiToolkitDbManager.get_instance().db
        is_table = True
        db_manager = AiToolkitDbManager.get_instance()

    ############################################### QUERIES ###############################################

    @classmethod
    def get_by_name(cls, name: str) -> "RagChatProfile | None":
        """The profile with this name, or None."""
        return cls.get_or_none(cls.name == name)

    @classmethod
    def get_all_ordered_by_name(cls) -> ModelSelect:
        """Every profile, in a stable order for a UI list or a select."""
        return cls.select().order_by(cls.name)

    @classmethod
    def get_by_publish_token(cls, token: str) -> "RagChatProfile | None":
        """The profile this publish token belongs to, or None.

        Does not filter on ``is_published``: ``unpublish_profile`` clears ``publish_token`` to
        ``None``, so a match already implies the profile is published. A caller that wants the
        invariant checked explicitly (rather than relying on that always holding) should still read
        ``is_published`` off the returned row — see
        :class:`~gws_ai_toolkit.api.knowledge_base_api_auth.PublishTokenAuth`.
        """
        return cls.get_or_none(cls.publish_token == token)

    ############################################### CONFIGURATION ###############################################

    def get_retrieval_config(self) -> RetrievalConfig:
        """The retrieval configuration this profile's searches run with.

        Mode and fusion constant are left at their defaults: they are engine-level choices, not
        something a profile author tunes.
        """
        return RetrievalConfig(top_k=self.top_k, score_threshold=self.score_threshold)

    def get_knowledge_base_ids(self) -> list[str]:
        """The configured knowledge-base ids, as stored.

        A row written by hand can hold ``None``, and a profile bound to nothing is a legitimate state
        (a profile is created before its knowledge bases are picked), so both read as an empty list
        rather than an error.
        """
        return list(self.knowledge_base_ids or [])

    ############################################### DTO ###############################################

    def to_dto(self) -> RagChatProfileDTO:
        """Convert to the DTO handed to Reflex states and HTTP responses.

        ``publish_token`` never appears here — see the field's own comment. The other publication
        columns are not secrets, so a configuration screen can show whether a profile is published.
        """
        return RagChatProfileDTO(
            id=self.id,
            name=self.name,
            system_prompt=self.system_prompt,
            model=self.model,
            top_k=self.top_k,
            score_threshold=self.score_threshold,
            knowledge_base_ids=self.get_knowledge_base_ids(),
            is_published=self.is_published,
            published_at=self.published_at,
            published_by_email=self.published_by.email if self.published_by else None,
            created_at=self.created_at,
            last_modified_at=self.last_modified_at,
        )
