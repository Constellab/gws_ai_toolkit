"""One chat profile as the UI shows it, shared by the list table and the detail page.

The row is built here rather than on either state so the two pages cannot disagree about what a
profile *is*: the same resolution of bound ids to names, the same distinction between "binds nothing"
and "binds something that has since been deleted", the same labels. It is also what
``rag_chat_profile_actions`` takes, which is what lets one action cluster serve a table row and a page
header without either page reimplementing it.
"""

from dataclasses import dataclass, field

from gws_ai_toolkit.models.knowledge_base.knowledge_base_dto import KnowledgeBaseDTO
from gws_ai_toolkit.models.knowledge_base.rag_chat_profile_dto import RagChatProfileDTO

# What is shown for a profile that set no score threshold, which is the default and not a missing
# value.
NO_THRESHOLD_LABEL = "—"


@dataclass
class ChatProfileRow:
    """One profile as the UI shows it, resolved server-side.

    The UI needs the *names* of the bound knowledge bases, which the profile only holds ids for, so
    the join happens here rather than in the browser. Two facts are carried rather than left to be
    inferred from an empty list, because they mean different things: a profile bound to nothing
    retrieves nothing, and a profile bound to a knowledge base that has since been deleted searches
    less than its author configured.

    Attributes:
        id: The profile's id.
        name: The profile's name.
        model: Its ``provider:model`` string.
        top_k_label: How many passages one search returns.
        threshold_label: The score a passage must reach, or :data:`NO_THRESHOLD_LABEL`.
        knowledge_base_names: Names of the bound knowledge bases that still exist, in bound order.
        is_unbound: True when the profile binds no knowledge base at all.
        has_dangling_bindings: True when it binds an id whose knowledge base no longer exists.
        is_published: True when this profile's bound knowledge bases are reachable through a
            publish token by anyone holding it.
        published_label: Human-readable "since when, by whom" for a published profile, empty
            otherwise.
    """

    id: str
    name: str
    model: str
    top_k_label: str
    threshold_label: str
    knowledge_base_names: list[str] = field(default_factory=list)
    is_unbound: bool = False
    has_dangling_bindings: bool = False
    is_published: bool = False
    published_label: str = ""


def build_chat_profile_row(
    profile: RagChatProfileDTO, knowledge_bases: list[KnowledgeBaseDTO]
) -> ChatProfileRow:
    """Resolve one profile against the knowledge bases that exist.

    :param profile: the profile to show
    :param knowledge_bases: every knowledge base of this lab, to resolve the bound ids against
    :return: the row the list table and the detail page both render
    """
    names_by_id = {knowledge_base.id: knowledge_base.name for knowledge_base in knowledge_bases}
    return ChatProfileRow(
        id=profile.id,
        name=profile.name,
        model=profile.model,
        top_k_label=str(profile.top_k),
        threshold_label=(
            NO_THRESHOLD_LABEL if profile.score_threshold is None else str(profile.score_threshold)
        ),
        knowledge_base_names=[
            names_by_id[bound_id]
            for bound_id in profile.knowledge_base_ids
            if bound_id in names_by_id
        ],
        is_unbound=not profile.knowledge_base_ids,
        has_dangling_bindings=any(
            bound_id not in names_by_id for bound_id in profile.knowledge_base_ids
        ),
        is_published=profile.is_published,
        published_label=build_published_label(profile),
    )


def build_published_label(profile: RagChatProfileDTO) -> str:
    """"Since when, by whom" for a published profile, or "" when it is not published.

    :param profile: the profile to describe
    """
    if not profile.is_published or profile.published_at is None:
        return ""

    since = profile.published_at.strftime("%Y-%m-%d")
    if profile.published_by_email:
        return f"Since {since} by {profile.published_by_email}"
    return f"Since {since}"


def empty_chat_profile_row() -> ChatProfileRow:
    """A row standing for "no profile loaded".

    The detail page's action cluster is rendered inside an ``rx.cond`` on the loaded profile, but the
    computed var behind it is evaluated either way — so it needs something to return before the page
    has loaded, and a row with no id is what the actions would refuse to act on anyway.
    """
    return ChatProfileRow(id="", name="", model="", top_k_label="", threshold_label="")
