# RAG migration — RAGFlow → LlamaIndex + LanceDB

> **Detailed implementation plan**: see
> [rag_embedded_stack_implementation_plan.md](rag_embedded_stack_implementation_plan.md) —
> code-grounded module/data-model/UI design, verified dependency pins, phased implementation order,
> and one **open decision** (external-document handling, pending the global data lab refactor in
> `gws_core/docs/todo/refactor/modular_apps_split_plan.md`).
> Settled since this doc was written: standalone module `rag/embedded/` (no `BaseRagService`),
> pydantic-ai chat loop in this brick, new chat entity named `RagChatProfile`, source-agnostic
> document storage via a `RagDocumentSource` registry with snapshot-on-add.

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
LLM          → the existing Pydantic AI agent (provider-configurable)
```

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

- **One LanceDB directory per index.** Community = one shared dir; per-lab = one dir
  per lab, created automatically at lab provisioning. Isolation is structural (a lab
  cannot read another lab's dir).
- **No server, no manual config.** Provisioning an instance = create a directory +
  run the ingestion code. Chunking / retrieval config lives in code, per instance
  type.
- **Ingestion / re-indexing** is a code job (initial index + refresh when docs or
  lab data change), not a UI action.

## Multi-dataset & per-query activation (Approach A: metadata filtering)

Several datasets can live in **one** LanceDB index, each chunk tagged with a
`dataset` metadata field (plus any other tags: `lang`, `visibility`…). A query
then **activates only chosen datasets** via a metadata filter — dynamic per
request, no reconfiguration. This is the equivalent of RAGFlow's "tick which
knowledge bases", in one line; LanceDB pushes the filter down to the store
(efficient, not a naive post-filter).

```python
# Ingestion: each document carries its dataset (and other tags)
doc.metadata = {"dataset": "product_docs", "lang": "en"}

# Query: activate only some datasets
from llama_index.core.vector_stores import (
    MetadataFilters, MetadataFilter, FilterOperator,
)

filters = MetadataFilters(filters=[
    MetadataFilter(key="dataset",
                   value=["product_docs", "api_reference"],
                   operator=FilterOperator.IN),
])
retriever = index.as_retriever(similarity_top_k=5, filters=filters)
```

- One index to manage; a chunk can belong to several datasets; combine tags
  (`dataset`, `lang`, `visibility`) freely.
- The activated subset is a **query parameter**, not a config change.

### How A relates to the per-instance (Approach B) design above

The two combine, and map onto this brick's layers:

```
Lab / Community boundary  → one LanceDB dir per instance   (physical isolation)
Inside a lab / Community  → one index + `dataset` filter    (soft, per-query)
```

- **Physical isolation (one dir per lab)** for the hard boundary between labs and
  between Community and a lab — isolation by construction, per the multi-instance
  design above.
- **Metadata filtering (Approach A)** for soft boundaries *inside* one index:
  content types in the same lab (product docs vs notes vs lab data), toggled
  per query.

**Security note:** do **not** rely on the metadata filter alone to isolate data
between users/labs. A filter is easy to forget or mis-pass, and then a query sees
everything. For a real privacy boundary (a lab's own data), use physical isolation
(a separate dir): what is not in the directory cannot leak. Keep metadata filtering
for convenience/scoping within an already-isolated index.

## Management layer: Datasets, Chats, and their binding

Beyond the RAG engine, this is a **RAG product**: three persisted first-class
objects, each with a management tool/UI. Everything lives in **this brick
(`gws_ai_toolkit`)**; the gws_core Pydantic AI agent stays the chat *engine*
called by the Chat service.

> Context from the existing brick (verify against code before building):
> `gws_ai_toolkit` already ships RAG integrations (Dify, RAGFlow) under `rag/` and
> a **standalone Reflex RAG app** (`apps/rag_app/_rag_app/`) with `chat/` and
> `agents/` components. The LlamaIndex+LanceDB engine and the objects below should
> **evolve that existing app**, not start from scratch.

**Decision: the entire RAG config app + the chat are Reflex**, in this brick. A
separate Angular chat may exist later but is handled externally — **out of scope**
for these plans.

### Data model (Peewee, in this brick)

```
Dataset ──< DatasetFile          a dataset = a set of indexed files
   │                             + ingestion config (chunking), index state
   │  (many-to-many)
   ▼
Chat ── config: bound datasets + prompt + top_k + provider/model …
   │
   └──< ChatMessage              conversation history, persisted per chat (V1)
```

- **Dataset** — name, description, files, chunking config, index status.
- **Chat** — name, **bound datasets**, prompt, provider/model, retrieval params.
- **ChatMessage** — per-chat history. **Persisted in DB from V1** (multiple chats
  must be listable and resumable) — this supersedes the "stateless V1" note in the
  gws_core agent plan.

### The key articulation: chat → datasets IS the metadata filter

"Configure each chat on some datasets" = the chat's *bound datasets* field becomes
the **`MetadataFilters`** of Approach A above. The chat→datasets binding stored in
DB is exactly what is passed as the `dataset` filter at query time. The management
layer and the retrieval layer connect through this one field.

### Tools to build

| Tool | Does |
|---|---|
| **Dataset manager** | list / create / **upload files** / re-index / delete a dataset |
| **Chat manager** | list / create / configure (bound datasets, prompt, model) / delete |
| **Chat window** | converse in a chat; retrieval scoped to that chat's bound datasets |

Layers: RAG (LlamaIndex/LanceDB) = retrieval; gws_core agent = chat loop;
this management layer (persisted datasets/chats) + Reflex UI sits on top.

## File formats & handling tabular data (JSON / Excel / CSV)

LlamaIndex has native loaders for PDF/MD/txt/DOCX/HTML **and** for Excel
(`PandasExcelReader`), CSV, JSON — so tabular files *can* be indexed. But RAG is
**semantic text similarity**, and a raw table row / JSON object
(`{"id":42,"status":"PAID","amount":1500}`) is a poor chunk: it resembles no
natural-language question, giving weak retrieval. Three handling modes:

| Mode | How | Good for |
|---|---|---|
| **1. Index as text** | each row → a sentence ("Investment #42 has status PAID, amount 1500€"); each sheet/object → a doc | **qualitative** questions over small/medium tables |
| **2. Summary + metadata** | index a *summary* (columns, stats, description); keep the raw file aside | finding *which* file/dataset is relevant |
| **3. Text-to-SQL / query engine** (NOT RAG) | load the table as DataFrame/SQL, **generate a query** instead of vector retrieval | **quantitative** questions (sum, average, precise filtering) |

**Vector RAG is not for analytics.** "How many / sum / average / filter precisely"
→ mode 3 (text-to-SQL), not RAG. Note gws_core already provides an analytical path
for DB data via the MCP `db_query` tool (read-only text-to-SQL) — so the agent has
capability 3 for in-database data already; the RAG here serves 1/2 (qualitative).

**V1 recommendation:** index **documents (PDF/MD/txt/DOCX/HTML) + tabular in text
mode (1)** — CSV/Excel/JSON converted to row-sentences at ingestion. Honest about
its limits; leave quantitative questions to `db_query` / a dedicated query engine.

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

## Open questions

- Reranking at launch? (API reranker vs local BGE-reranker vs none for V1.)
- Refresh strategy: full re-index vs incremental on doc/data change.
- Per-lab RAG scope: which lab data is indexed (resources, notes, files?) and how
  access control maps to the connected user.
- Where this brick's RAG service is exposed to the agent (MCP tool vs in-process
  LlamaIndex tool) — align with the agent plan in gws_core.
