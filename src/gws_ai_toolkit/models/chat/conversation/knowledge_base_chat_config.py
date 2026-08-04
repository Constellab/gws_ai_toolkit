"""What one knowledge-base chat run is configured with.

A :class:`~gws_ai_toolkit.models.knowledge_base.rag_chat_profile.RagChatProfile` is the persisted,
user-selectable form of this; :class:`KnowledgeBaseChatConfig` is the value a run actually needs. The
two are kept apart on purpose:

- the chat loop never holds a Peewee row, so it stays picklable on a Reflex state and usable from an
  HTTP route that resolved its profile some other way;
- ``knowledge_base_ids`` here is the **resolved** binding — dangling ids already dropped by
  :meth:`~gws_ai_toolkit.models.knowledge_base.rag_chat_profile_service.RagChatProfileService.get_valid_knowledge_base_ids`
  — so the retrieval path never has to wonder whether its filter still points at anything;
- a test can build one without writing a row.

Naming follows the convention recorded in ``rag_chat_profile_dto``: ``*Config`` for a non-persisted
module DTO, *profile* for the row.
"""

from gws_core import BaseModelDTO

from gws_ai_toolkit.models.knowledge_base.rag_chat_profile import RagChatProfile
from gws_ai_toolkit.models.knowledge_base.rag_chat_profile_dto import (
    DEFAULT_CHAT_PROFILE_MODEL,
    DEFAULT_CHAT_PROFILE_SYSTEM_PROMPT,
)
from gws_ai_toolkit.models.knowledge_base.rag_chat_profile_service import RagChatProfileService
from gws_ai_toolkit.rag.knowledge_base.knowledge_base_config import DEFAULT_TOP_K


class KnowledgeBaseChatConfig(BaseModelDTO):
    """The configuration of one knowledge-base chat, taken from a profile but not tied to its row.

    Attributes:
        chat_profile_id: Id of the profile this configuration was read from. Persisted in the
            conversation's ``chat_configuration``, and the only thing a restore needs.
        model: pydantic-ai ``provider:model`` string, resolved by ``AiModelFactory``.
        system_prompt: Instructions handed to the model, which is where the obligation to search
            before answering is stated.
        top_k: Maximum number of passages one search returns.
        score_threshold: Minimum score a passage must reach, on the retrieval mode's own scale.
            ``None`` means no threshold — see ``RagChatProfile.score_threshold`` for why no numeric
            default is safe.
        knowledge_base_ids: The knowledge bases a search is scoped to, dangling ids already dropped.
            An empty list retrieves nothing rather than everything.
    """

    chat_profile_id: str
    model: str = DEFAULT_CHAT_PROFILE_MODEL
    system_prompt: str = DEFAULT_CHAT_PROFILE_SYSTEM_PROMPT
    top_k: int = DEFAULT_TOP_K
    score_threshold: float | None = None
    knowledge_base_ids: list[str] = []

    @classmethod
    def from_profile(cls, profile: RagChatProfile) -> "KnowledgeBaseChatConfig":
        """Read a run's configuration off a profile row, resolving its binding on the way.

        The binding is resolved here rather than by the caller so that every entry point — the chat
        window, a restore, the future HTTP route — searches exactly the knowledge bases that still
        exist, instead of each remembering to filter.

        Args:
            profile: The profile the chat runs with.

        Returns:
            The configuration of a run against that profile.
        """
        return cls(
            chat_profile_id=profile.id,
            model=profile.model,
            system_prompt=profile.system_prompt,
            top_k=profile.top_k,
            score_threshold=profile.score_threshold,
            knowledge_base_ids=RagChatProfileService().get_valid_knowledge_base_ids(profile),
        )
