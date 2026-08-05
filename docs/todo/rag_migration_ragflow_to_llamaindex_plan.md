# RAG migration — RAGFlow → LlamaIndex + LanceDB

> This document holds the **rationale and stack choice**. The work is planned in three companion
> documents, reviewed August 2026:
>
> - [pydantic_ai_agent_migration_plan.md](pydantic_ai_agent_migration_plan.md) — **prerequisite**:
>   every hand-rolled OpenAI agent loop in this brick moves to pydantic-ai first.
> - [rag_embedded_stack_implementation_plan.md](rag_embedded_stack_implementation_plan.md) — engine,
>   data model, UI, sync, and the removal of Dify/RAGFlow.
> - [knowledge_base_public_api_plan.md](../done/knowledge_base_public_api_plan.md) — the HTTP route the
>   Constellab Community backend calls.
>
> **Terminology settled**: the container of indexed documents is a **`KnowledgeBase`** (not
> "dataset" — that word already means a lab resource, experimental data, and the retired platforms'
> own knowledge bases). A configured chat is a **`RagChatProfile`**. Documents are supplied through a
> `KnowledgeBaseDocumentSource` registry with snapshot-on-add.
>
> **Also settled**: Dify and RAGFlow are removed from this brick in the same refactor, taking
> `BaseRagService` and the service factories with them; there is no coexistence period and no feature
> flag.

## Goal

Replace RAGFlow with a **lightweight, code-driven, embeddable** RAG stack that can
be **provisioned automatically, with no manual configuration**, and run as
**many independent instances**:

- **Community-level (global)** — one shared index over Constellab product / dev docs.
- **Per data lab (later)** — one index per lab so a user can query **their own data
  inside their lab**, isolated by construction.

The multi-instance, auto-provisioned requirement is what drives the stack choice:
an embedded engine + embedded vector store, not a server platform with a UI to
administer.

## Chosen stack

```
LlamaIndex   → RAG engine (ingestion, chunking, retrieval), driven in Python code
LanceDB      → embedded vector store: one directory = one index (the "SQLite of
               vector stores") → one per lab, created by code, no server to run
Embeddings   → via API (multilingual by default, e.g. text-embedding-3)
LLM          → a pydantic-ai agent (provider-configurable via `provider:model` strings)
```

⚠️ The gws_core pydantic-ai agent **does not exist** — it is planned in
`gws_core/docs/todo/refactor/ai_agent_chat_plan.md`. The chat loop therefore lives in this brick, and
this brick's three existing hand-rolled OpenAI loops migrate to pydantic-ai **first**, so the
knowledge-base chat is written once on a shared base rather than adding a second paradigm. See
[pydantic_ai_agent_migration_plan.md](pydantic_ai_agent_migration_plan.md).

Retrieval is exposed to the agent as a **tool** (e.g. `search_knowledge(query)`);
the agent (Pydantic AI) still owns the chat loop (memory, streaming, tool calls).
LlamaIndex is the retrieval layer, not a second chat engine — no duplication.

## Why this replaces RAGFlow without losing capability

RAGFlow does not *own* these features — it pre-wires and exposes chunkers /
embeddings / rerankers / LLM behind a UI. LlamaIndex gives the **same building
blocks in code**. What is lost is the configuration/monitoring **UI** (replaced by
code config + our own logs) and the out-of-the-box pre-wiring (replaced by a few
lines assembled once). What is gained is exactly the requirement: lightweight,
trivially multi-instance, versionable config, zero manual setup.

### Chunking — same control (or more)

| RAGFlow | LlamaIndex equivalent |
|---|---|
| Chunk templates (general, Q&A, paper, book, table…) | Splitter choice per doc type |
| Size + overlap | `SentenceSplitter(chunk_size, chunk_overlap)` |
| "Smart" / semantic chunking | `SemanticSplitterNodeParser` |
| Structure-aware (titles, tables) | Markdown / HTML / code / hierarchical parsers |
| — (not possible in UI) | Custom splitter logic in code |

Medium differs: RAGFlow = pick a template in a menu; here = set `chunk_size` /
swap splitter in config. For automated multi-lab, this is an advantage: a chunking
config per lab type, versioned in code, no clicks.

### Chat — same levers

| RAGFlow chat config | LlamaIndex equivalent |
|---|---|
| Prompt / persona | `system_prompt`, prompt templates |
| Top-K retrieved passages | `similarity_top_k` |
| Similarity threshold | node postprocessors (cutoff) |
| Reranking | built-in rerankers (Cohere API, BGE-reranker local…) |
| Query rewriting | query transforms |
| Citations / sources | `CitationQueryEngine` |
| Conversation memory | chat engines with history (here: owned by the agent) |

## Cross-lingual: French questions over English files

**Supported**, and it hinges on one thing: the **embedding model must be
multilingual**. A FR question and the EN passage about the same topic must land at
the same place in vector space; a multilingual embedding does exactly that, with
no translation step.

- With the chosen **API embeddings** (e.g. OpenAI `text-embedding-3`), multilingual
  is the default → FR→EN retrieval works out of the box.
- The only failure mode would be an English-only embedding model (would then need
  query translation) — not the case with standard API embeddings.
- The **LLM** then receives English passages + a French question and answers in
  French naturally.

So: multilingual embedding for cross-lingual *retrieval*, LLM for *answering* in
the question's language. Both covered by the stack.

## Multi-instance design

- **One LanceDB directory per instance**, at `knowledge_base/instances/<scope>/`. Isolation is
  structural: an instance cannot read another instance's directory.
- **No server, no manual config.** Provisioning = create a directory and index. Embedding config is
  **instance-level** (one shared vector space, recorded in a manifest table keyed by scope and
  validated fail-closed on open); chunk size and overlap are **per knowledge base**.
- **Ingestion is both** a UI action (upload, "Sync now") and a provider-driven sync — the earlier
  "code job, not a UI action" framing was wrong for the product this became.

### The Community instance is a lab, not a separate platform

Worth recording, because it was not obvious: the Community chatbot **already runs in a data lab**.
`rag/ragflow/ragflow_start_docker_compose.py` starts RAGFlow as a docker compose stack inside a lab
via Constellab's `DockerService`, and `gws_core`'s `CommunityUserService.ask_ragflow_chatbot` calls
`POST {community_api_url}/ragflow-chatbot/ask` — the Community backend fronts it.

So "community-level" is not a different deployment model: it is **one lab that serves external
callers**, and what it needs is an authenticated HTTP route. Hence
[knowledge_base_public_api_plan.md](../done/knowledge_base_public_api_plan.md). Note also that removing
RAGFlow from this brick does **not** retire that deployment — repointing it is coordinated work in the
Community codebase.

## Multiple knowledge bases & per-query activation (Approach A: metadata filtering)

Several knowledge bases can live in **one** LanceDB index, each chunk tagged with a
`knowledge_base_id` metadata field (plus any other tags: `lang`, `access_scope`…). A query then
**activates only chosen knowledge bases** via a metadata filter — dynamic per request, no
reconfiguration. This is the equivalent of RAGFlow's "tick which knowledge bases", in one line;
LanceDB pushes the filter down to the store (efficient, not a naive post-filter).

```python
# Ingestion: each document carries its knowledge base (and other tags)
doc.metadata = {"knowledge_base_id": "<kb id>", "lang": "en", "access_scope": "*"}

# Query: activate only some knowledge bases
from llama_index.core.vector_stores import (
    MetadataFilters, MetadataFilter, FilterOperator,
)

filters = MetadataFilters(filters=[
    MetadataFilter(key="knowledge_base_id",
                   value=["<kb id>", "<other kb id>"],
                   operator=FilterOperator.IN),
])
retriever = index.as_retriever(similarity_top_k=5, filters=filters)
```

- One index to manage; combine tags (`knowledge_base_id`, `lang`, `access_scope`) freely.
- The activated subset is a **query parameter**, not a config change.
- ⚠️ **Verify the push-down holds in hybrid mode**, where results come from two retrievers and are
  fused. This is the isolation mechanism between knowledge bases, so it needs a dedicated test rather
  than an assumption.

### How A relates to the per-instance (Approach B) design above

The two combine, and map onto this brick's layers:

```
Instance boundary  → one LanceDB dir per scope        (physical isolation)
Inside an instance → one index + knowledge_base_id filter   (soft, per-query)
```

- **Physical isolation (one dir per scope)** for the hard boundary between deployments — isolation by
  construction, per the multi-instance design above. It is also what forces one embedding space per
  instance, since everything in a directory must be comparable.
- **Metadata filtering (Approach A)** for soft boundaries *inside* one instance: content types in the
  same lab (product docs vs notes vs lab data), toggled per query.

**Security note:** do **not** rely on the metadata filter alone to isolate data between users. A
filter is easy to forget or mis-pass, and then a query sees everything. For a real privacy boundary,
use physical isolation: what is not in the directory cannot leak. Keep metadata filtering for
convenience and scoping within an already-isolated instance.

This is why the externally-reachable route derives its scope from a **publish token** rather than a
caller-supplied id — with no per-document access control in V1, a caller-supplied knowledge-base id
would be exactly the "forget the filter" failure, reachable from outside the lab.

## Management layer: knowledge bases, chat profiles, and their binding

Beyond the RAG engine, this is a **RAG product**: three persisted first-class objects, each with a
management tool/UI. Everything lives in **this brick (`gws_ai_toolkit`)**, including the chat loop —
the gws_core agent it would eventually delegate to does not exist yet.

> Context from the existing brick: `gws_ai_toolkit` ships RAG integrations (Dify, RAGFlow) under
> `rag/` and a **standalone Reflex RAG app** (`apps/rag_app/_rag_app/`). The new engine and objects
> **evolve that existing app** — the generic chat widget, conversation persistence and history sidebar
> are reused as-is — while the two platform integrations and their service abstractions are removed.

**Decision: the management app and the in-lab chat are Reflex**, in this brick. Externally, the
Community website consumes the HTTP route rather than a Reflex page — see
[knowledge_base_public_api_plan.md](../done/knowledge_base_public_api_plan.md). A separate Angular chat, if it
happens, would consume the same route.

### Data model (Peewee, in this brick)

```
KnowledgeBase ──< KnowledgeBaseDocument   a KB = a set of indexed documents
   │                                      + ingestion config (chunking), index state
   │  (many-to-many)
   ▼
RagChatProfile ── bound knowledge bases + prompt + top_k + provider/model …
   │
   └──< ChatMessage                       conversation history, persisted per chat (V1)
```

- **KnowledgeBase** — name, description, documents, chunking config, index status.
- **RagChatProfile** — name, **bound knowledge bases**, prompt, provider/model, retrieval params.
- **ChatMessage** — per-chat history. **Persisted in DB from V1** (multiple chats must be listable
  and resumable) — this supersedes the "stateless V1" note in the gws_core agent plan. Since the
  chat loop keeps history **client-side** (no OpenAI `previous_response_id`), these rows are what the
  model sees on restore, so tool turns are persisted too.

### The key articulation: chat → knowledge bases IS the metadata filter

"Configure each chat on some knowledge bases" = the profile's *bound knowledge bases* field becomes
the **`MetadataFilters`** of Approach A above. The binding stored in DB is exactly what is passed as
the filter at query time. The management layer and the retrieval layer connect through this one
field.

⚠️ Because that filter is the only thing separating knowledge bases inside one index, it must be
verified to push down in **hybrid** (vector + full-text) mode as well as pure vector mode. A filter
that silently fails open there is a correctness bug, not a performance one.

### Tools to build

| Tool | Does |
|---|---|
| **Knowledge-base manager** | list / create / **upload documents** / re-index / sync / delete |
| **Chat-profile manager** | list / create / configure (bound KBs, prompt, model) / publish / delete |
| **Chat window** | converse in a chat; retrieval scoped to that profile's bound knowledge bases |

Layers: LlamaIndex/LanceDB = retrieval; pydantic-ai = chat loop; this management layer (persisted
knowledge bases and chat profiles) + Reflex UI sits on top; the HTTP route is a second consumer of the
same chat loop.

## File formats & handling tabular data (JSON / Excel / CSV)

LlamaIndex has native loaders for PDF/MD/txt/DOCX/HTML **and** for Excel
(`PandasExcelReader`), CSV, JSON — so tabular files *can* be indexed. But RAG is
**semantic text similarity**, and a raw table row / JSON object
(`{"id":42,"status":"PAID","amount":1500}`) is a poor chunk: it resembles no
natural-language question, giving weak retrieval. Three handling modes:

| Mode | How | Good for |
|---|---|---|
| **1. Index as text** | each row → a sentence ("Investment #42 has status PAID, amount 1500€"); each sheet/object → a doc | **qualitative** questions over small/medium tables |
| **2. Summary + metadata** | index a *summary* (columns, stats, description); keep the raw file aside | finding *which* file or table is relevant |
| **3. Text-to-SQL / query engine** (NOT RAG) | load the table as DataFrame/SQL, **generate a query** instead of vector retrieval | **quantitative** questions (sum, average, precise filtering) |

**Vector RAG is not for analytics.** "How many / sum / average / filter precisely"
→ mode 3 (text-to-SQL), not RAG. Note gws_core already provides an analytical path
for DB data via the MCP `db_query` tool (read-only text-to-SQL) — so the agent has
capability 3 for in-database data already; the RAG here serves 1/2 (qualitative).

**V1 decision (revised): documents only.** PDF / MD / txt / DOCX / HTML, plus RichText JSON (note
content, converted to Markdown by `RagResource`). **CSV, Excel and data JSON are rejected at add
time** with a clear message.

Mode 1 was the earlier recommendation and was dropped for three compounding reasons:

- At the 15 MB cap, a CSV is easily 100k+ rows. Row-sentences make that **100k chunks inside one
  document**, at 100k embeddings' worth of cost.
- Those chunks are near-identical in form, so they match *everything* weakly — degrading retrieval for
  the PDFs and notes that share the index. The failure mode is not "tables answer badly", it is
  "everything answers slightly worse".
- The questions people actually ask a table (count, sum, filter, compare) are exactly the ones vector
  RAG cannot do. `db_query` covers them for data **in the lab database**, but an uploaded CSV is not
  there — so mode 1's honest scope is small tables of qualitative text, which a 15 MB cap does not
  suggest.

Follow-ups if a real need appears, in order of preference: a **column summary** chunk per table
(columns, dtypes, row count, ranges, samples — makes a table *findable* without polluting the space,
and needs no LLM call), then row-level indexing behind an explicit row cap.

## Trade-offs vs RAGFlow (honest)

- Lose the ingestion/config/test **UI** and visual monitoring → replaced by code + logs.
- Lose out-of-the-box pre-wiring → assemble the pipeline once ourselves.
- Some advanced RAGFlow options (exotic document parsing, knowledge graph) exist in
  the LlamaIndex ecosystem but must be wired in explicitly.

## Embeddings decision & caveats

- **Chosen: API embeddings** — zero infra, high quality, multilingual by default.
- **Caveat (privacy):** the per-lab RAG queries a user's own lab data → API embeddings
  send that content to a third party, per-token cost. Revisit local embeddings
  (BGE / sentence-transformers via `fastembed`, nothing leaves the lab) if per-lab
  data sensitivity requires it. Design the embedding layer swappable from the start.

## Resolved (August 2026)

- **Reranking at launch?** No reranker. Instead **hybrid retrieval** — vector + full-text search,
  fused with a model-free strategy. LanceDB already pulls `tantivy`, so full-text is nearly free, and
  it fixes a failure embeddings genuinely have: exact terms (error codes, gene names, ids). A reranker
  adds either a second vendor and credential (Cohere) or `sentence-transformers` + torch (local BGE) —
  revisit when a real query retrieves the right document but ranks it badly. The node-postprocessor
  seam stays in place so one drops in without an interface change.
- **Refresh strategy.** Incremental, driven by a **content hash** rather than `last_modified_at`, so a
  no-op save no longer triggers re-embedding. Full re-index remains an explicit operation (and is
  forced by an embedding-model change).
- **Where the retrieval tool lives.** In-process pydantic-ai agent tool (`search_knowledge`), not MCP.
- **Access control.** Out of scope for V1: `gws_core` has no per-object permissions today, so there is
  nothing to derive a scope from. Chunks carry `access_scope = "*"` as a reserved field. The V1
  boundary is app access, plus the publish token for externally-reachable profiles.

## Still open

- **Which lab data is indexed** beyond tag-selected resources (notes, files) — driven by the source
  registry, so each is an additive provider rather than a design change.
- **Who may create, delete or publish a knowledge base.** No permission model exists; publishing is
  the sharper case, since a published profile is readable by anyone holding its token.
- **Local embeddings** for privacy-sensitive per-lab data (the caveat below). `EmbeddingFactory` is
  the single swap point.
