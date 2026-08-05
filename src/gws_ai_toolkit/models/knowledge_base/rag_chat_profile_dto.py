"""DTOs and defaults of the chat-profile layer.

A chat profile is the one place where the management layer and the retrieval layer meet: its bound
knowledge bases *are* the metadata filter a retrieval runs with. Everything else it holds — the
system prompt, the model, ``top_k``, ``score_threshold`` — is per-query configuration that touches
nothing on disk.

Naming: ``*Config`` is reserved for non-persisted module DTOs (``KnowledgeBaseChatConfig``); a
persisted, named, user-selectable row is a **profile**.
"""

from gws_core import BaseModelDTO, ModelDTO

from gws_ai_toolkit.rag.knowledge_base.knowledge_base_config import DEFAULT_TOP_K

# pydantic-ai ``provider:model`` string, as every model-naming surface of this brick uses.
DEFAULT_CHAT_PROFILE_MODEL = "openai:gpt-4.1-mini"

# The two things a knowledge-base chat gets wrong unless it is told otherwise: it answers from its
# own memory instead of searching, and it answers in the documents' language instead of the user's.
DEFAULT_CHAT_PROFILE_SYSTEM_PROMPT = """You are a knowledge assistant answering questions about a curated set of documents.

Always call the `search_knowledge` tool before answering a question about those documents, even when \
you believe you already know the answer: your own memory is not the source of truth here. Search \
again with different wording when the first passages are not enough.

Ground every statement in the retrieved passages, and say plainly when they do not contain the \
answer rather than filling the gap.

Answer in the language the user writes in, whatever language the documents are written in."""


class RagChatProfileDTO(ModelDTO):
    """A chat profile as the UI and the HTTP layer see it.

    ``knowledge_base_ids`` is reported exactly as stored, dangling ids included: a configuration
    screen has to show what was configured, and the drop happens at query time (see
    :meth:`~.rag_chat_profile_service.RagChatProfileService.get_valid_knowledge_base_ids`).

    The row's publication columns are deliberately absent: the publish workflow is separate work, and
    ``publish_token`` is a credential that must never travel to a Reflex state.
    """

    name: str
    system_prompt: str
    model: str
    top_k: int
    score_threshold: float | None = None
    knowledge_base_ids: list[str]


class SaveRagChatProfileDTO(BaseModelDTO):
    """Input of a chat-profile create or update."""

    name: str
    system_prompt: str = DEFAULT_CHAT_PROFILE_SYSTEM_PROMPT
    model: str = DEFAULT_CHAT_PROFILE_MODEL
    top_k: int = DEFAULT_TOP_K
    # No default value is safe here — see RagChatProfile.score_threshold.
    score_threshold: float | None = None
    knowledge_base_ids: list[str] = []
