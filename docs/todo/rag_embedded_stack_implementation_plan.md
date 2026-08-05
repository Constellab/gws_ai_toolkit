# Implementation plan — embedded knowledge-base stack (LlamaIndex + LanceDB)

> Rationale and stack choice: [rag_migration_ragflow_to_llamaindex_plan.md](rag_migration_ragflow_to_llamaindex_plan.md).
> **Blocked on** [pydantic_ai_agent_migration_plan.md](pydantic_ai_agent_migration_plan.md) — the chat
> loop is built on the migrated agent base, not alongside it.
> The Community-facing HTTP surface is [knowledge_base_public_api_plan.md](../done/knowledge_base_public_api_plan.md).
> Rewritten August 2026 after a full review of the earlier draft. Move all four docs to `docs/done/`
> once implemented.
> **Step-1 spike run August 2026** — its findings are folded into *Spike results* under §Hybrid
> retrieval, and they changed two decisions (fusion named, `score_threshold` redefined, engine reads
> the LanceDB table directly). The probe itself is captured on the throwaway branch
> **`spike/lancedb-hybrid`** under `spike_lancedb/` (`./run.sh`, deterministic, no API key) — see
> its `FINDINGS.md`. That branch is a primary source, **never merged**.

## What this rewrite changes, and why

The earlier draft opened with "✅ Open decision — RESOLVED by the core document index", deferring to
`gws_core/docs/todo/refactor/document_management_plan.md`. **That resolution does not hold as a V1
plan**, for two verifiable reasons:

- **The core document index does not exist in code.** `IndexedDocumentModel`, `DocumentProvider`,
  `document_index` and `entity_type_decorator` appear nowhere in `gws_core/src`. Its own sequencing
  puts "RAG integration" at step **7 of 9**, behind an entity-type registry that document itself
  calls *"a bigger job than the index itself… probably its own plan document"*.
- **Its amendments deleted V1's only ingestion paths.** `add_uploaded_document` and the built-in
  `upload` provider were dropped in favour of "admin upload goes through the drive" — and the drive
  is step 5 of that same unbuilt plan. As written, V1 could ingest zero documents.

So the core plan describes the **target** architecture, not this deliverable. This document builds a
standalone stack that adopts `document_index` later as **one additional source provider** — which is
exactly what the provider registry exists for.

Superseded decisions from the earlier draft, for the record:

| Earlier draft | Now |
|---|---|
| Blocked on / resolved by the core document index | Standalone; `document_index` becomes a later source provider |
| `snapshot_path` → `content_hash` (snapshots dropped) | Snapshots **kept**; the hash becomes the version marker |
| `access_scope` mandatory, two triggers + cross-process queue + SQL backstop | No access filtering in V1; `access_scope = "*"` reserved in chunk metadata |
| "All writes happen in the Reflex app process only" (documented rule) | `fcntl.flock` on the instance dir; any process may write |
| `RagDataset` / `RagDatasetFile` | `KnowledgeBase` / `KnowledgeBaseDocument` |
| Dify/RagFlow untouched, removal a later release | Both deleted in this refactor, with `BaseRagService` |
| Tabular indexed as row-sentences | Documents only; tabular rejected at add time |
| Reranking an open question | Hybrid search (vector + FTS) in V1; no reranker |
| One instance, multi-instance documented only | Multi-instance built and tested; per-lab deployment shipped |

## Context (verified against code, August 2026)

- **Chat seam is Reflex-free.** `models/chat/conversation/base_chat_conversation.py` imports no
  Reflex; its single abstract method is `_call_ai_chat(user_message) -> Generator[ChatMessage]`, with
  `build_current_message()` (streaming deltas) and
  `close_current_message(external_id=None, sources=list[RagChatSource])`. Reflex coupling lives in
  `apps/rag_app/.../chat_base/conversation_chat_state_base.py`. This is what lets the UI and the HTTP
  route share one loop.
- **Chat history is already persisted** via `AiToolkitDbManager`: `ChatConversation` /
  `ChatMessageModel` / `ChatMessageSourceModel`. `ChatMessageModel` already carries
  `type CharField(20)` + `data JSONField(null=True)`, so tool-turn persistence needs **no
  migration**.
- **`ChatConversationMode`** is `RAG | AI_EXPERT | AI_TABLE` (`base_chat_conversation.py:21-24`).
- **`RagResource`** (`rag/common/rag_resource.py`) holds the reusable compatibility rules and the
  RichText JSON → Markdown conversion. Kept.
- **Apps run as separate, transient OS processes**: `AppsManager.running_processes` keyed by app id
  with `MAX_RUNNING_APPS` (`apps_manager.py:45,110`), stopped on idle via `set_stop_policy` /
  `AppStopPolicy` (`:502`). `AppDirLocks` documents the matching precedent: a `threading` lock
  suffices only because app starts share one process, and *"should apps ever be started from several
  processes, this must be replaced by a cross-process lock (`fcntl.flock`)"*.
- **The brick exposes no HTTP routes today** (no `APIRouter`, no `core_app`).
- Reflex 0.9.5.post2 via gws_core; brick pins `gws_core` 0.23.0 (installed 0.23.8).

## Decisions (settled)

1. **Standalone module** `rag/knowledge_base/`. The core `document_index` is a future source
   provider, not a dependency.
2. **Chat loop on pydantic-ai**, on the migrated agent base — retrieval exposed as an agent tool.
3. **Snapshots kept, hash as version marker.** A snapshot is the *only* copy of an uploaded document
   and the reason re-indexing never contacts a source system. `source_version` holds a content hash,
   so a no-op save no longer triggers re-embedding.
4. **No access filtering in V1**, `access_scope = "*"` written into chunk metadata as a reserved
   field. See *Access control* below.
5. **`fcntl.flock` around LanceDB access**; any process may write.
6. **Documents only.** PDF / MD / TXT / DOCX / HTML, plus RichText JSON (note content). CSV, XLSX and
   data JSON are rejected at add time.
7. **Hybrid retrieval** — vector + full-text, fused with LanceDB's `RRFReranker` (`k = 60`), which is
   model-free arithmetic. **No cross-encoder or hosted reranking model.** The engine reads the
   LanceDB table directly so it sees the real fused score — see *Spike results*.
8. **Multi-instance is built**, not documented-only. Per-lab deployment ships; the community
   deployment is the public-API plan.
9. **Dify and RAGFlow are deleted**, with `BaseRagService` and the factories.

## 1. Module `src/gws_ai_toolkit/rag/knowledge_base/`

```
knowledge_base_config.py       EmbeddingConfig (provider "openai"|"mock", model, api_key, dimensions)
                               + ChunkConfig (chunk_size 1024, overlap 100) + RetrievalConfig
                               (top_k, score_threshold, fusion strategy)
knowledge_base_models.py       RetrievedChunk DTO (chunk_id, content, score, knowledge_base_id,
                               document_id, filename) + .to_rag_chat_source() → existing RagChatSource
embedding_factory.py           EmbeddingFactory.create(config) → OpenAIEmbedding | deterministic mock
                               (hashed bag-of-words) for tests. Single swap point for local models.
document_loader.py             DocumentLoader.load(path, metadata) per extension:
                               txt/md → text; pdf → PDFReader; docx → DocxReader (legacy .doc
                               rejected — docx2txt cannot parse it); html → BeautifulSoup strip;
                               json → RichText→markdown via RagResource, else REJECTED.
                               csv/xlsx/data-json → REJECTED at add time with a clear message.
                               Metadata on every Document: knowledge_base_id, document_id, filename,
                               access_scope (all excluded from embedded/LLM text).
knowledge_base_engine.py       KnowledgeBaseEngine(instance_dir, embedding_config) — one dir = one
                               instance. All public methods synchronous, all writes flock-guarded.
knowledge_base_storage.py      Disk layout + instance resolution (see §7)
knowledge_base_credentials.py  resolve_openai_api_key(credentials_name) → CredentialsDataOther
                               → fallback Settings.get_open_ai_api_key()
sources/
├── knowledge_base_source.py       KnowledgeBaseDocumentSource ABC + registry
├── upload_source.py               "upload" provider (built-in)
└── resource_source.py             "resource" provider (the ONLY file importing RagResource)
```

### Engine surface

```
index_document(path, knowledge_base_id, document_id, filename, chunk_config) -> int
delete_document(document_id) / delete_knowledge_base(knowledge_base_id)
retrieve(query, knowledge_base_ids, top_k, score_threshold,
         document_ids=None) -> list[RetrievedChunk]
count_chunks(knowledge_base_id=None)
```

`document_ids` narrows a search to specific documents rather than whole knowledge bases. It is not
speculative: **AI Expert's `relevant_chunks` mode requires it** — today it calls
`rag_service.retrieve_chunks(..., document_ids=[document_id])`, and that method is being deleted. It
is a second `MetadataFilter` on the same push-down path as `knowledge_base_id`.

AI Expert's other mode, `full_text_chunk`, reads the **document snapshot** directly instead of
reassembling chunks — exact text, no chunk-boundary artefacts, no engine call. So the deleted
`get_document_chunks` needs no engine equivalent; add one only if something else asks for an ordered
chunk listing.

`index_document` deletes the document's existing chunks first, so it is idempotent and safe to retry
after an interruption. The LanceDB delete predicate is encapsulated in one private `_delete_where`.

### Concurrency: flock, not a documented rule

Every write acquires `fcntl.flock` on a lock file in the instance directory; reads take a shared
lock. The earlier draft's "writes only in the Reflex app process" cannot hold: several app instances
are a normal deployment (`rag_app` and `full_app` both exist), the writer is killed on idle, and the
HTTP route reads from the server process. A comment cannot enforce any of that.

This also removes the need for the core plan's cross-process deletion queue: a server-side listener
can eventually write directly under the same lock.

### Hybrid retrieval

Vector search plus a full-text (tantivy) index over chunk text, fused with a model-free strategy
(reciprocal rank fusion or linear combination). This fixes exact-term lookups — error codes, gene
names, task ids — that embeddings handle poorly, with no extra vendor, credential or model.

### Spike results (August 2026) — settled, do not re-litigate

Run against `lancedb 0.36.0`, `llama-index-core 0.14.23`, `pyarrow 24.0.0`, `pandas 2.3.3`,
`tantivy 0.26.0`, with a deterministic mock embedding. All four step-1 questions are answered.

| Question | Answer |
|---|---|
| **`MetadataFilters` push-down in hybrid mode** | ✅ **Works.** Verified in vector, FTS *and* hybrid mode, at both layers — raw `where(pred, prefilter=True)` and llama-index `MetadataFilters`. A canary term present only in knowledge base B never leaks into a query filtered to A. The isolation mechanism holds. |
| **Second filter (`document_ids`)** | ✅ **Works**, same push-down path — `knowledge_base_id = 'x' AND document_id = 'y'` narrows correctly. AI Expert's `relevant_chunks` mode is safe to build on it. |
| **FTS incrementality** | ✅ **No maintenance step needed.** Rows added after index creation are immediately full-text searchable — LanceDB scans the unindexed fragment. `table.optimize()` and `create_fts_index(replace=True)` both also work. **The write path needs no explicit optimise call**, contradicting the earlier assumption. Watch the cost as the unindexed tail grows; batching stays a follow-up, not a prerequisite. |
| **Delete predicate** | ✅ Flat column, `IN (...)` lists and backticked identifiers all work. **Single quotes in a value must be doubled** (`'doc_o''brien'`) — the one thing `_delete_where` genuinely has to encapsulate, since filenames and ids reach it from user input. |

**Fusion strategy: LanceDB's `RRFReranker`, default `k = 60`.** Note the vocabulary clash that
decision 7 walks into: LanceDB calls hybrid fusion a *"reranker"*. `RRFReranker` and
`LinearCombinationReranker` (default `weight = 0.7`) are pure arithmetic — no model, no vendor, no
credential. So "hybrid search, no reranker" means **no cross-encoder or hosted reranking model**; we
do use RRF fusion, and the plan must name it rather than appear to forbid it.

Also: `create_fts_index` is deprecated as of lancedb 0.25.0 — use `create_index(config=FTS())`.

### ⚠️ `score_threshold` cannot live at the llama-index layer

The one negative finding, and it changes a column's meaning. `LanceDBVectorStore.query()` does not
return the fused score — it returns **rank position rescaled to 0..1**. Same query, same corpus:

```
top_k=2  ->  [1.0, 0.0]
top_k=3  ->  [1.0, 0.5, 0.0]
top_k=4  ->  [1.0, 0.6667, 0.3333, 0.0]
top_k=6  ->  [1.0, 0.8, 0.6, 0.4, 0.2, 0.0]
```

The top hit is always `1.0`, the last always `0.0`, evenly spaced regardless of relevance. A
threshold applied to that number cannot mean *"relevant enough"* — only *"in the top slice"* — and
its meaning silently shifts every time `top_k` changes. Reading the raw table directly gives the real
fused score: `_relevance_score` from RRF, ~0.015–0.033 in this corpus, rank-derived and **not
comparable to a cosine similarity** (`_distance` in vector mode, `_score`/BM25 in FTS mode).

Two consequences, both settled here:

- **The engine reads the LanceDB table directly** rather than going through
  `LanceDBVectorStore.query()`, so `score_threshold` applies to `_relevance_score`. The wrapper also
  nests our metadata under a `metadata: struct<...>` column, which makes every predicate
  `metadata.document_id = '...'`; owning the table keeps the flat schema §7 assumes. llama-index
  stays in the picture for `document_loader.py` (readers, chunking, `Document`), which is what it is
  actually good for here.
- **`RagChatProfile.score_threshold` is documented against the RRF score**, default `None`. Do not
  carry over a cosine-tuned value: on this scale a `0.5` threshold rejects everything.

Untested, because it only matters if the wrapper is kept after all: deleting by predicate against the
wrapper's **nested** `metadata` struct.

### Embedding manifest — fail closed

Embedding config is an **instance-level** property; chunk size and overlap are per knowledge base.
Several knowledge bases share one LanceDB instance separated only by a metadata filter, so they must
share one vector space.

Changing model or dimensions silently corrupts retrieval in the dangerous direction: a width change
errors loudly, but `text-embedding-3-large` at `dimensions=1536` — or a `mock`↔`openai` swap — has
the *same width in a different space*. No error, plausible-looking scores, near-random chunks.

Guard, held in the DB (see §3): the engine validates the manifest row on open.

- **No row** → adopt current config and write the row (first run, or an adopted directory).
- **Row differs** → refuse to read *or* write, naming expected vs actual.

Re-indexing after an intentional model change is then an explicit, logged operation.

### Document sources

The knowledge-base layer never knows about lab resources or other apps:

```python
class KnowledgeBaseDocumentSource(ABC):
    source_type: str                       # "upload", "resource", later "document_index"

    @abstractmethod
    def fetch_file(self, source_id, source_metadata) -> SourceFetchResult:
        """Fresh local copy (filename + temp path + version marker). Called at add and
        refresh/sync time — NEVER at index time. Conversions happen here."""

    @abstractmethod
    def get_version_marker(self, source_id, source_metadata) -> str | None:
        """Content hash. None = source gone/unavailable."""

    def get_open_action(self, document) -> SourceOpenAction | None:
        """How the chat UI opens this document. Default: download the snapshot."""

    def list_documents(self, sync_config: dict) -> list[SourceDocumentCandidate]:
        """Optional: enumerate for bulk sync (default: unsupported)."""

    @classmethod
    def register(cls) -> None: ...

class KnowledgeBaseDocumentSourceRegistry:
    get(source_type) / all()
```

- **`upload`**: the uploaded bytes *are* the snapshot; no version marker, no sync.
- **`resource`**: wraps `RagResource` — compatibility pre-checks, RichText→Markdown in `fetch_file`,
  `get_open_action` = share-link redirect, `list_documents` = the tag search (§6).
- **Other bricks** register their own provider at brick load; this brick never imports them — the
  same inversion `@credentials_type` uses.
- Generic compatibility (supported extension, ≤15 MB) is applied by the service on the **fetched
  file**, source-agnostically.

### Access control (V1)

`gws_core` has **no per-object permissions** — `AuthorizationService` does authentication only,
`UserGroup` is a flat SYSUSER < ADMIN < USER hierarchy, and any lab user sees everything. There is
nothing for V1 to derive a scope from, so the whole apparatus in the earlier draft (perimeter-change
events, cross-process metadata queue, SQL id verification) is out of scope — it existed to keep a
scope fresh that cannot be populated.

**V1 boundary: whoever can open the app sees everything in it.** Two rules:

- `access_scope = "*"` is written into every chunk's metadata now. Reserving the field costs one line
  and avoids re-embedding the entire store when real scopes arrive.
- **Constraint to state in the docs and UI: do not index documents whose readership is narrower than
  the app's.** For a published profile this is sharper still — see the public-API plan.

## 2. Removing Dify and RAGFlow

**Delete**

```
rag/dify/                              (whole package)
rag/ragflow/                           (whole package, incl. the docker-compose task)
rag/common/base_rag_service.py
rag/common/base_rag_app_service.py
rag/common/rag_service_factory.py
rag/common/rag_app_service_factory.py
rag/common/datahub_rag_app_service.py
rag/common/tag_rag_app_service.py      (query logic salvaged first — see §6)
rag/common/rag_credentials.py
rag/common/rag_enums.py
rag/common/rag_models.py               → keep ONLY RagChatSource, RagChatSourceChunk
models/chat/conversation/rag_chat_config.py
models/chat/conversation/rag_chat_conversation.py
apps/rag_app/.../reflex/rag_chat/      (folder)
apps/rag_app/generate_datahub_ragflow_app.py  + its __init__ export
```

**Keep** — `RagChatSource` / `RagChatSourceChunk` (persisted by `ChatMessageSourceModel`, drive the
source-pill UI and chunk dialog), `RagResource`, and the whole `chat_base/` + `ChatConversation`
layer.

**No data migration is needed.** Confirmed August 2026: every indexed document exists as a **tagged
lab resource**, so the whole corpus is re-indexable from source through the `resource` provider. There
is nothing that lives only inside a Dify or RAGFlow dataset.

⚠️ **Scope note**: this removes RAGFlow from *this brick*. The Community chatbot is a separate
lab-hosted deployment fronted by the Community backend — see the public-API plan.

### Feature parity

| Behaviour | Fate |
|---|---|
| Tag-driven resource sync (`TagRagAppService.get_all_resources_to_send_to_rag`) | **Partially reimplemented**: the tag search becomes the `resource` provider's `list_documents`, driving a one-shot import (§6). The standing subscription — untag removes, content change re-indexes — is deferred to v2 |
| Marked-for-deletion workflow (`get_resources_marked_for_deletion`, `is_resource_marked_for_deletion`, `delete_resource_from_rag_and_lab`) | **Reimplemented** (§6). Destructive — deletes from the lab, not only the knowledge base |
| DataHub / S3 sync (`DatahubRagAppService` + `GenerateDatahubRagFlowApp`) | **Dropped**, no replacement scope |
| Per-app default chat filters (`get_chat_default_filters`) | **Dropped** — subsumed by the profile → knowledge-base binding |
| AI Expert's chunk sources (`retrieve_chunks`, `get_document_chunks`) | **Repointed**, not dropped — `relevant_chunks` → `engine.retrieve(..., document_ids=[id])`; `full_text_chunk` → read the snapshot. AI Expert is a consumer of `BaseRagService`, so it cannot outlive it |
| AI Expert `full_file` mode (OpenAI upload + hosted code interpreter) | **Removed as a product decision** — see [pydantic_ai_agent_migration_plan.md](pydantic_ai_agent_migration_plan.md). Unrelated to this brick's RAG backend, but it is what makes AI Expert's port trivial |

### Legacy conversations

`ChatConversationMode` gains `KNOWLEDGE_BASE = "knowledge_base"`. `RAG = "rag"` is **retained as
legacy-only**: existing rows stay listable in history, but their `configuration` points at retired
RAGFlow datasets, so a restore attempt must show *"this conversation used a retired engine"* rather
than fail opaquely. Do not reuse `"rag"` for the new stack.

## 3. Data model — `src/gws_ai_toolkit/models/knowledge_base/`

Conventions follow `models/chat/`: subclass `gws_core.Model`, `Meta.table_name`,
`Meta.database = AiToolkitDbManager.get_instance().db`, `is_table = True`,
`db_manager = AiToolkitDbManager.get_instance()` — tables auto-create at brick load, no migration.

```
KnowledgeBase ──< KnowledgeBaseDocument      one KB = N indexed documents
     ▲                    └── row id == chunk-metadata `document_id` in LanceDB
     │ (knowledge_base_ids JSON list — soft M2M)
RagChatProfile                                a configured chat bound to N knowledge bases
     │ (chat_configuration["chat_profile_id"])
ChatConversation ──< ChatMessageModel ──< ChatMessageSourceModel      (EXISTING — reused)

EmbeddingManifest                             one row per engine instance
```

### `KnowledgeBase` — `gws_ai_toolkit_knowledge_base`

| column | type | notes |
|---|---|---|
| id / created_at / last_modified_at | inherited | id = 36-char uuid PK |
| name | `CharField(100, unique=True)` | |
| description | `TextField(default="")` | |
| instance_scope | `CharField(50, default="default")` | which engine instance holds its chunks (§7) |
| chunk_size | `IntegerField(default=1024)` | per KB |
| chunk_overlap | `IntegerField(default=100)` | per KB |
| sync_source_type | `CharField(50, null=True)` | **reserved for sync v2** — provider for the standing subscription; written by nothing in V1 |
| sync_config | `JSONField(null=True)` | **reserved for sync v2** — provider-specific scope (resource: `{tag_key, tag_value}`) |

The two `sync_*` columns ship unused: V1 imports by tag as a one-shot action (§6) and takes its criterion
from the dialog, not from the row. They stay in the schema because they already shipped, and leaving them
saves a migration when v2 lands.

### `KnowledgeBaseDocument` — `gws_ai_toolkit_knowledge_base_document`

| column | type | notes |
|---|---|---|
| knowledge_base | `ForeignKeyField(KnowledgeBase, backref="documents", on_delete="CASCADE")` | |
| source_type | `CharField(50)` | open provider key — not an enum |
| source_id | `CharField(100, null=True)` | opaque id in the source system; null for uploads |
| source_metadata | `JSONField(null=True)` | provider extras |
| source_version | `CharField(100, null=True)` | **content hash** at snapshot time |
| snapshot_path | `CharField(512)` | always set; indexing reads only this |
| filename | `CharField(255)` | shown in source pills |
| size | `BigIntegerField(default=0)` | snapshot bytes |
| index_status | `CharField(20, default="pending")` | `pending` \| `indexing` \| `done` \| `error` |
| indexing_started_at | `DateTimeField(null=True)` | **lease** — see below |
| error_message | `TextField(null=True)` | |
| chunk_count | `IntegerField(default=0)` | |
| indexed_at | `DateTimeField(null=True)` | |

**The row id is the `document_id` in every chunk's LanceDB metadata.**

**Snapshot-on-add invariant**: populated for every row via `provider.fetch_file(...)`. Indexing never
contacts the source, so a deleted resource or an unavailable app breaks neither retrieval nor
re-indexing. Accepted trade-offs: storage duplication (bounded by the 15 MB cap) and staleness — a
snapshot updates only on explicit refresh. A source that disappears leaves its snapshot in place — a
V1 import never deletes anything (§6); reaping those rows is sync v2's job.

**Indexing lease.** Indexing runs in a Reflex background event, and that process is killed on idle —
so without a lease an interrupted run leaves `index_status = "indexing"` forever: a permanent
spinner, ambiguous re-index semantics, and possibly half-written chunks. `indexing_started_at` is
stamped when the status is set; a row whose lease exceeds the threshold is reported as
`error` ("interrupted, retry") and is reclaimable on next load or sync. Re-indexing is idempotent
(chunks are deleted first), so reclaiming is always safe. A real task queue stays a follow-up.

### `RagChatProfile` — `gws_ai_toolkit_rag_chat_profile`

| column | type | notes |
|---|---|---|
| name | `CharField(100, unique=True)` | |
| system_prompt | `TextField(default=...)` | instructs tool use + answering in the user's language |
| model | `CharField(100, default="openai:gpt-4.1-mini")` | pydantic-ai `provider:model` |
| top_k | `IntegerField(default=5)` | |
| score_threshold | `FloatField(null=True)` | **defined against the RRF `_relevance_score`** (~0.015–0.033 scale, rank-derived), not a cosine similarity. Default `None` |
| knowledge_base_ids | `JSONField(default=list)` | bound KBs — **becomes the LanceDB `MetadataFilters`** at query time. Soft M2M: validated on save, dangling ids dropped at query time; join table is a follow-up |
| is_published / publish_token / published_at | | see [knowledge_base_public_api_plan.md](../done/knowledge_base_public_api_plan.md) |

`*Config` is reserved for non-persisted module DTOs (`AiExpertChatConfig`); a persisted, named,
user-selectable row is a **profile**. `RagChatConfig` frees up when RAGFlow is deleted — do not
reuse it here.

### `EmbeddingManifest` — `gws_ai_toolkit_embedding_manifest`

| column | type | notes |
|---|---|---|
| instance_scope | `CharField(50, unique=True)` | keyed from day one — a single-row table becomes silently wrong the moment a second instance exists |
| provider / model | `CharField` | |
| dimensions | `IntegerField` | |

Known limitation: the vectors live on disk while the invariant lives in MariaDB, so a LanceDB
directory copied or restored independently arrives with no row. The "no row → adopt and write"
rule covers it; a directory restored against a *different* database is caught as a mismatch.

### Services

- **`KnowledgeBaseService`** (mutations under `@AiToolkitDbManager.transaction()`; talks only to the
  source registry):
  - knowledge-base CRUD;
  - `add_uploaded_document(kb_id, filename, bytes)` — writes the snapshot, row with
    `source_type="upload"`, status `pending`;
  - `add_document(kb_id, source_type, source_id, source_metadata)` — `fetch_file` → generic
    compatibility check → snapshot → row with `source_version`, status `pending`;
  - `refresh_document(document_id)` — re-fetch, replace snapshot, update hash, status `pending`;
  - `index_document(document_id, engine)` — status transitions + lease; reads only `snapshot_path`;
  - `reclaim_stale_leases()`;
  - `delete_document` (chunks + snapshot + row); `delete_knowledge_base` (chunks + files dir + rows);
  - `import_documents(kb_id, source_type, criteria, engine) -> ImportReport` (§6).
- **`RagChatProfileService`**: CRUD, `get_valid_knowledge_base_ids(profile)`, publish/un-publish.

### Non-DB DTOs

`EmbeddingConfig`, `ChunkConfig`, `RetrievalConfig`, `RetrievedChunk`, `KnowledgeBaseDTO`,
`KnowledgeBaseDocumentDTO`, `RagChatProfileDTO` (+ `Save*` inputs), `ImportReport`,
`SourceFetchResult`, `SourceDocumentCandidate`, `SourceOpenAction`. Reflex states consume DTOs, never
Peewee rows.

## 4. Chat loop — `models/chat/conversation/knowledge_base_chat_conversation.py`

`KnowledgeBaseChatConversation(BaseChatConversation[ChatUserMessageText])`, mode
`knowledge_base`, `chat_configuration={"chat_profile_id": ...}` for restore. Built on the migrated
pydantic-ai base — see [pydantic_ai_agent_migration_plan.md](pydantic_ai_agent_migration_plan.md).

- `Agent(model=profile.model, instructions=profile.system_prompt, deps_type=RetrievalDeps)`, provider
  key injected explicitly (no reliance on process env).
- `@agent.tool search_knowledge(ctx, query)` → `engine.retrieve(query, knowledge_base_ids, top_k,
  score_threshold)`; appends to `deps.collected_chunks`; returns formatted passages.
- `_call_ai_chat`: yield user message → stream deltas via `build_current_message(delta, append=True)`
  → on completion `close_current_message(sources=deduped [c.to_rag_chat_source()])`; errors →
  `ChatMessageError`.
- **History is client-side**, persisted including tool turns (`type = "tool_call"` /
  `"tool_result"` in `ChatMessageModel.data`). No `previous_response_id`.
- **Never hold a live engine or LanceDB connection on state or conversation objects** across events
  (picklability). Build the engine lazily per operation — `lancedb.connect` on a local dir is cheap.
- Agent construction overridable for tests (`TestModel` / `FunctionModel`, no API calls).

## 5. Reflex UI — `apps/rag_app/_rag_app/rag_app/reflex/knowledge_base/`

Existing component/state folder convention, relative imports, default button colours, red for
destructive.

- `core/knowledge_base_app_state.py` — shared helpers (build engine for an instance, resolve API key
  from params).
- `knowledge_bases/` — list (+create/delete); detail with a document table (source-type chip, status
  chip incl. *interrupted*, chunk count, error tooltip, per-document re-index/refresh/delete); upload
  component (`rx.upload.root` + `rx.upload_files`,
  pattern from `ai_table_standalone_app/home_page.py`; background event indexes pending documents);
  add-document dialog (source-type select from the registry; the resource provider contributes a
  resource picker with compatibility feedback, plus an **import-by-tag mode** whose report is a dialog
  — a tag matching fifty resources of which eight are incompatible must not read as a clean success).
  **Rejected extensions are reported at add time with the reason**, not silently skipped.
- `chats/` — profile list + edit (prompt, model, top_k, threshold, knowledge-base multi-checkbox,
  publish/un-publish with the token shown once).
- `chat/` — `KnowledgeBaseChatState(ConversationChatStateBase)`, mirroring the retired
  `RagChatState`: `_create_conversation` / `_restore_conversation` from the profile id in
  `configuration`; `_after_conversation_updated` → history refresh + `replaceState`; override
  `open_document` to delegate to `provider.get_open_action(document)` (resource → share link,
  default → `rx.download` of the snapshot). Header: profile selector. Reuses `chat_base` +
  `rag_page_layout_component` + history sidebar.

**Routes** (`rag_app.py`): `/kb`, `/kb/chat/[conversation_id]`, `/kb/bases`,
`/kb/bases/[knowledge_base_id]`, `/kb/chats`. The old `/rag*` routes are removed with the old stack,
so **no feature flag is needed** — coexistence was only necessary while both stacks lived. Extend the
history sidebar's mode→route mapping for `knowledge_base` and keep the legacy `rag` mode pointing at
a read-only notice.

**Generator task**: `apps/rag_app/generate_knowledge_base_app.py` — `GenerateKnowledgeBaseApp(Task)`,
replacing `GenerateDatahubRagFlowApp`: `chat_app_name`, optional
`CredentialsParam(CredentialsDataOther)` for the OpenAI key, admin-history/auth flags. Re-export from
the brick's top-level `__init__.py`.

## 6. Import and deletion — provider-driven

**V1 imports by tag as a one-shot action, not a standing subscription.** A knowledge base carries no
sync configuration; the criterion comes from the dialog and is used once. Membership state lives in
`KnowledgeBaseDocument` rows (`source_id` + `source_version`), never in the source system — legacy
`rag_document` / `rag_dataset_id` / `rag_sync` bookkeeping tags are **not** written.

`KnowledgeBaseService.import_documents(kb_id, source_type, criteria, engine) -> ImportReport`, valid for
any provider implementing `list_documents`:

1. `candidates = provider.list_documents(criteria)`.
2. Candidate whose `source_id` already has a row in this knowledge base → skip, "already present". This
   dedupe is the whole of the reconciliation logic, and it is cheap because `source_id` is on the row.
3. Otherwise `add_document` (fetch + snapshot), then index.
4. Incompatible format or over the size cap → skip with the reason (the existing service-level check on
   the fetched file).
5. Return `ImportReport` (added / skipped-with-reason) → dialog. **Report what was skipped and why** — a
   silent skip reads as success.

**An import never deletes.** A resource that left the tag keeps its document until someone removes it by
hand; per-document `refresh_document` covers content changes, and its hash check means a no-op save costs
no re-embedding.

**The `resource` provider** implements `list_documents` as the tag search salvaged from
`TagRagAppService.get_all_resources_to_send_to_rag()` (`ResourceSearchBuilder`: tag filter + fs-node
+ not-archived), with `version_marker` = content hash of the fetched file.

Each imported row stamps its criterion into `source_metadata`
(`{"imported_from": {"tag_key": ..., "tag_value": ...}}`). Without it an imported document is
indistinguishable from a hand-picked one, and sync v2 could not tell what is in its scope and what it
must never touch — one dict key now, no schema change later.

### Why the standing subscription is deferred

Reconciliation (new → add, hash changed → refresh, no longer a candidate → **delete** chunks + snapshot +
row) needs a persistent scope on the knowledge base, and it makes editing that scope a destructive
operation: narrowing a tag deletes documents, clearing the source orphans them. That is a feature with its
own confirmation semantics, and it does not have to land with the provider. V1 gets the same corpus into a
knowledge base with a bulk add; v2 keeps it current.

### Marked-for-deletion workflow (reimplemented)

Salvaged from `TagRagAppService`, which is deleted:

- a tag marks a lab resource for deletion;
- the knowledge-base detail page lists the pending deletions, computed **per document**: for each row
  with `source_type = "resource"`, does the resource behind its `source_id` carry the marker tag? No sync
  configuration is involved — the marker is its own tag, unrelated to whatever tag a document was
  imported by — so this covers hand-picked resource documents too;
- confirming removes the document from the knowledge base **and deletes the lab resource**.

⚠️ Destructive and irreversible. Keep it behind an explicit confirmation naming the resource, and
keep the "delete from lab" step visually distinct from "remove from knowledge base".

## 7. Disk layout and instances

```
<brick_extension_dir>/gws_ai_toolkit/knowledge_base/
├── instances/<scope>/lancedb/          vector + FTS indexes for that instance
├── instances/<scope>/.lock             flock target
└── files/<knowledge_base_id>/<document_id>_<sanitised_filename>    snapshots
```

Resolved via `BrickService.get_brick_extension_dir("gws_ai_toolkit", "knowledge_base")` — ⚠️ the
signature is `(brick_name, extension_name)`; verify at implementation whether a nested sub-path is
accepted, else join sub-directories onto the returned dir.

`instances/<scope>/` is **built and tested now**, not documented-only: `scope` comes from
`KnowledgeBase.instance_scope`, the engine takes the instance dir as a constructor argument, and the
embedding manifest is keyed by scope. V1 ships `default`; a per-lab or community deployment is a
different scope with no engine change.

## 8. Dependencies

`bricks/gws_ai_toolkit/settings.json`: bump `"version"` to `0.5.0`, bump `gws_core` to the release
carrying the `openai` bump, **remove `ragflow-sdk`**, and add:

```json
{ "name": "llama-index-core",                  "version": "..." },
{ "name": "llama-index-vector-stores-lancedb", "version": "..." },
{ "name": "lancedb",                           "version": "..." },
{ "name": "llama-index-embeddings-openai",     "version": "..." },
{ "name": "llama-index-readers-file",          "version": "..." },
{ "name": "docx2txt",                          "version": "..." }
```

`pydantic-ai-slim[openai]` is added by the agent-migration plan, not here.

**Pins verified by the August 2026 spike** — `lancedb 0.36.0` and `llama-index-core 0.14.23`
install and run **against gws_core's exact `pyarrow 24.0.0` and `pandas 2.3.3`**, so there is no
conflict to resolve. `tantivy 0.26.0` comes in transitively. The `>=0.13,<0.15` core constraint holds.

Still to re-verify at implementation time: `llama-index-readers-file` (needs `pandas<3`, pulls
`pypdf`, wants `beautifulsoup4`) and `llama-index-embeddings-openai`, neither of which the spike
installed. `lancedb` pulls `pylance` + `tantivy` (sizeable Rust wheels — accepted, and `tantivy` is
what makes hybrid search free).

Notes: do **not** add the `llama-index` meta package. Pin `lancedb` explicitly even though it comes
in transitively, so upgrades are deliberate. `docx2txt` is a runtime requirement of `DocxReader`.

## 9. Verification

Tests in `tests/test_gws_ai_toolkit/`, fixtures under `tests/testdata/knowledge_base/`. Run per file
from the brick directory: `gws server test <file>`.

1. `test_knowledge_base_engine.py` — mock embedding; index md/txt/html/richtext-json; **knowledge-base
   metadata-filter isolation in both vector and hybrid mode** (a query on A never returns B's
   chunks); **`document_ids` filter** narrows to one document within a knowledge base (AI Expert's
   `relevant_chunks` path); `delete_document` scoping; re-index idempotency; score threshold on the
   fused score;
   **embedding-manifest mismatch refuses to open**; **two instances in the same test** prove the
   scope parameter; rejected extensions raise with a clear message; FR-over-EN case skipped unless
   `OPENAI_API_KEY`.
2. `test_knowledge_base_service.py` — temp instance dir; upload/index status transitions incl. the
   error path; **stale-lease reclaim**; delete cleanup (chunks + snapshot); profile CRUD + dangling
   ids; a test-only `FakeDocumentSource` proves `add_document` / `refresh_document` /
   `import_documents` work against an unregistered-in-production provider; snapshot invariant (indexing
   still works after the fake source "disappears"); `ImportReport` reports skips, and a second import of
   the same criterion adds nothing.
3. `test_knowledge_base_chat_conversation.py` — `store_conversation_in_db=False`; `TestModel` /
   `FunctionModel` forcing a `search_knowledge` call; assert the yield sequence user → streaming* →
   `ChatMessageSource` with sources; **restore replays tool turns**; error path.
4. Manual: `gws reflex run .../rag_app/_rag_app/dev_config.json`, then
   `xvfb-run python take_screenshot.py --route /kb/bases|/kb/chats|/kb`; full loop — create KB →
   upload md → done → create profile → chat → source pill → reload `/kb/chat/<id>`. Then
   `ruff check --fix` on modified files.

## 10. Implementation order

Each step is independently verifiable. The two plans **interleave**: AI Expert's surviving modes need
this engine, so its port sits between steps 2 and 3 here — see
[pydantic_ai_agent_migration_plan.md](pydantic_ai_agent_migration_plan.md) *Ordering* for the combined
sequence.

0. **Agent migration steps 0–4** — gws_core `openai` bump, `full_file` removal, table and env agents
   ported, tool-turn persistence. The knowledge-base chat (step 3 below) is built on that base, so it
   does not start first.
1. **Deps + engine** — settings.json, install. ~~Spike~~ **done August 2026** (see *Spike results*):
   delete predicate, FTS incrementality, fusion strategy and hybrid metadata-filter push-down are all
   settled, so this step is now straight implementation of `rag/knowledge_base/`; engine tests green
   (including the manifest and two-instance cases). The mock embedding and the two-knowledge-base
   canary corpus lift straight out of the spike.
2. **Models + services** — `models/knowledge_base/`, `KNOWLEDGE_BASE` mode, manifest table, lease
   reclaim; service tests green (incl. `FakeDocumentSource` and the upload provider).
   → **AI Expert ported and repointed here** (agent-migration step 6), against
   `retrieve(..., document_ids=[...])` and the snapshot.
3. **Chat loop** — conversation class, credentials helper, conversation tests green.
4. **UI: knowledge-base manager** — routes, upload + index end to end in the dev app.
5. **UI: chat profiles + chat window** — full manual loop with restore.
6. **Resource provider + import by tag + marked-for-deletion** — verify with tagged lab resources:
   import → query → modify → refresh → query → re-import adds nothing → mark for deletion → confirm.
   Tag-driven sync is a follow-up (v2), not part of this step.
7. **Remove Dify/RAGFlow** (§2) — after the new stack is proven, so rollback stays possible until
   then. Grep for every deleted symbol; run the full suite. Re-index the corpus from the tagged
   resources.
8. **Packaging + docs** — generator task, facade exports, brick CLAUDE.md routes. Public API is its
   own plan.

## Risks

- ~~**Hybrid-mode metadata filtering**~~ — **resolved by the spike**: it pushes down in all three
  modes. Keep the isolation test in `test_knowledge_base_engine.py` as a regression guard, since a
  lancedb upgrade could regress it.
- ~~**LanceDB delete-predicate syntax**~~ — **resolved**: flat columns work. `_delete_where` still
  earns its keep by doubling single quotes in values.
- ~~**FTS index maintenance**~~ — **resolved**: no explicit optimise step needed. The residual risk is
  cost, not correctness: the unindexed-fragment scan grows until `optimize()` runs, so batching may
  still be wanted if indexing feels slow.
- **Reading the LanceDB table directly** (rather than through `LanceDBVectorStore`) means we own the
  query construction, including the RRF reranker wiring and the arrow schema. That is the price of a
  usable `score_threshold`; it also means a lancedb API change hits our code rather than being
  absorbed by llama-index. `create_fts_index` is already deprecated in favour of
  `create_index(config=FTS())`.
- ~~Data loss on deleting Dify/RAGFlow~~ — not a risk: the whole corpus is tagged lab resources and
  re-indexable from source.
- **Synchronous indexing in Reflex background events** (accepted, existing pattern). The lease bounds
  the damage; a task queue is the follow-up.
- **`knowledge_base_ids` JSONField has no FK integrity** — service-side validation; M2M follow-up.
- **Snapshot trade-offs** (accepted): storage duplication and staleness until explicit refresh.
- **Embedding cost and privacy**: per-lab documents are sent to OpenAI for embedding. The embedding
  layer is swappable (`EmbeddingFactory`) if local models become necessary.
- **Scope**: this refactor now spans an agent migration, a new engine and data model, and a public
  API. The three documents exist so each can land and be reviewed separately.

## Open items

- **Who may create or delete a knowledge base?** There is no permission model; any lab user with app
  access can currently do both. Publishing is the sharper case — see the public-API plan.
- **`document_index` provider**: to be added once the core index exists, as one more registry entry.
  Nothing in this plan needs to change for it.
- Whether `RagChatProfile` should be renamed once "Rag" stops being the module's vocabulary.
