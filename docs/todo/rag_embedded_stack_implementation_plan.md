# Implementation plan — embedded RAG stack (LlamaIndex + LanceDB + Pydantic AI)

> Detailed implementation plan for the RAG migration whose rationale and stack decision live in
> [rag_migration_ragflow_to_llamaindex_plan.md](rag_migration_ragflow_to_llamaindex_plan.md).
> Grounded in the existing code (July 2026). Move both docs to `docs/done/` once implemented.

## ⚠️ Open decision (blocking for external-document handling — NOT settled)

**How external documents are referenced and fetched depends on the global data lab refactor
(`gws_core/docs/todo/modular_apps_split_plan.md`), which is not decided yet.** That refactor splits
gws_core into core + workflow + note + form with the golden rule "an app never imports another app —
only the core": `ResourceModel`/`FSNodeModel`/`FileStore` move to `gws_workflow`, cross-app entities
become soft `(entity_type, entity_id)` references (no FK), and cross-app collaboration goes through
core-owned registries/events (`EntityLink`, deletion policies).

Impact on this plan — to be decided once the refactor lands (or is abandoned):

- **The `resource` document-source provider**: today it would wrap `RagResource`/`ResourceModel`
  directly; post-refactor, "a lab resource" lives in `gws_workflow` and may only be referenceable as
  `(entity_type, entity_id)` through a core registry. The provider may need to be registered BY
  `gws_workflow` (or a bridge brick) rather than shipped in `gws_ai_toolkit`.
- **Reference format**: whether `RagDatasetFile.source_id` should adopt the refactor's
  `(entity_type, entity_id)` convention from day one, and whether dataset→document links should be
  `EntityLink` rows (with a deletion policy) instead of plain columns.
- **Deletion semantics**: whether deleting a source entity should RESTRICT/CASCADE/DETACH its RAG
  dataset files (the refactor's deletion-policy mechanism) or keep the "snapshot survives, sync
  removes later" behavior specified below.

**What is safe to build now regardless**: the engine, datasets, uploads, chat — and the
`RagDocumentSource` registry itself, which already follows the refactor's target pattern
(registration at brick load, opaque string references, no cross-brick imports, graceful degradation
when a provider is absent). Only the `resource` provider implementation and its sync (§6 resource
specifics) should wait for — or be revisited after — the refactor decision.

## Context

`gws_ai_toolkit` currently integrates two external RAG platforms (Dify, RagFlow) behind
`BaseRagService`, driven by the Reflex RAG app. This plan replaces them with a lightweight,
embeddable, auto-provisionable stack: **LlamaIndex (ingestion/retrieval) + LanceDB (embedded vector
store) + OpenAI multilingual embeddings + Pydantic AI (chat loop)**.

### Key exploration findings

- **The gws_core Pydantic AI agent does not exist yet** — only planned
  (`gws_core/docs/todo/ai_agent_chat_plan.md`). → V1 chat loop lives in this brick, aligned with that
  plan (`provider:model` strings, `CredentialsDataOther` keys) so it can migrate later.
- **The chat stack has a clean seam**: generic chat widget (`reflex/chat_base/`) →
  `ConversationChatStateBase` (streaming state mixin; subclasses implement
  `_create_conversation`/`_restore_conversation`) → `BaseChatConversation` whose single abstract
  method is `_call_ai_chat(user_message) -> Generator[ChatMessage]` (verified). Helpers:
  `build_current_message()` (streaming deltas), `close_current_message(sources=list[RagChatSource])`
  (persists final text/source message).
- **Chat history is already persisted locally** (Peewee via `AiToolkitDbManager`):
  `ChatConversation`/`ChatMessageModel`/`ChatMessageSourceModel` (stores `RagChatSource` DTOs) —
  provider-agnostic, reused as-is. Emitting `RagChatSource` keeps the source-pill UI and chunk dialog
  working unchanged.
- **Resource sync** is tag-based (`RagResource`: ext txt/pdf/docx/doc/md/json, 15 MB cap, RichText
  JSON→Markdown) — compatibility rules and file conversion are reused; RAGFlow bookkeeping tags are
  NOT.
- Reflex 0.9.5 (from gws_core 0.23.0); `rx.upload` pattern already used in
  `ai_table_standalone_app`. `RagChatConfig` name already taken → new chat entity named
  **`RagChatProfile`**.

## Decisions (settled)

1. **Standalone module** (`rag/embedded/`) — does NOT implement `BaseRagService`; Dify/RagFlow code
   untouched (removal is a later release).
2. **Chat loop: pydantic-ai in this brick**, retrieval exposed as an agent tool.
3. **Data model: new dataset tables + reuse existing chat persistence.**
4. **V1 sources: both** file upload (new UI) and lab-resource sync. Engine is multi-instance by
   construction (one LanceDB dir per instance, constructor param); V1 ships one instance under the
   brick data dir; per-lab provisioning = documented follow-up.
5. **Document storage is source-agnostic**: no structural dependency on lab resources. Documents may
   be manual uploads, lab resources, or documents from other apps/bricks (e.g. gws_project — not
   importable from this brick, so sources are an extension point). Every document is **snapshotted
   into the brick filestore at add time**; indexing always reads the snapshot. Origins are pluggable
   via a `RagDocumentSource` provider registry.

---

## 1. New module `src/gws_ai_toolkit/rag/embedded/`

```
embedded_rag_config.py        EmbeddingConfig (provider "openai"|"mock", model text-embedding-3-small,
                              api_key, dimensions) + ChunkConfig (chunk_size 1024, overlap 100)
embedded_rag_models.py        RetrievedChunk DTO (chunk_id, content, score, dataset_id, document_id,
                              filename) + .to_rag_chat_source() → reuses rag/common RagChatSource DTOs
embedding_factory.py          EmbeddingFactory.create(config) → OpenAIEmbedding | deterministic mock
                              (hashed bag-of-words) for tests — single swap point for future local models
document_loader.py            DocumentLoader.load(path, metadata) per extension:
                              txt/md → text Document; pdf → PDFReader; docx → DocxReader
                              (legacy .doc NOT supported — docx2txt can't parse it; rejected at add-file);
                              html → BeautifulSoup strip; json → RichText→markdown (reuse RagResource
                              logic) else row-sentences; csv/xlsx → pandas row-sentences.
                              Metadata on every Document: dataset_id, document_id, filename
                              (ids excluded from embed/LLM text). Supported ext + 15MB cap constants.
embedded_rag_engine.py        EmbeddedRagEngine(db_dir, embedding_config) — one LanceDB dir = one instance.
                              index_file(path, dataset_id, document_id, filename, chunk_config) → int
                                (SentenceSplitter → insert_nodes; deletes old chunks first = idempotent)
                              delete_document(id) / delete_dataset(id)  (encapsulate LanceDB delete
                                predicate in one private _delete_where — layout verified by step-1 tests)
                              retrieve(query, dataset_ids, top_k, score_threshold) → list[RetrievedChunk]
                                (MetadataFilters IN on dataset_id + optional SimilarityPostprocessor)
                              count_chunks(dataset_id=None)
embedded_rag_storage.py       Disk layout under BrickService.get_brick_extension_dir("gws_ai_toolkit",
                              "embedded_rag/..."): lancedb/ (default instance) + files/<dataset_id>/
                              (snapshots of ALL documents, whatever their origin)
embedded_rag_credentials.py   resolve_openai_api_key(credentials_name) → CredentialsDataOther["api_key"]
                              → fallback Settings.get_open_ai_api_key() (env)
sources/                      document-source extension point (see below)
├── rag_document_source.py    RagDocumentSource ABC + registry
├── upload_document_source.py "upload" provider (built-in no-op)
└── resource_document_source.py  "resource" provider (the ONLY file importing RagResource)
```

All engine methods are synchronous (same blocking-in-background-event pattern as existing OpenAI
code).

### Document sources — `rag/embedded/sources/`

The dataset layer never knows about lab resources or other apps; it talks to a provider registry:

```python
class RagDocumentSource(ABC):
    source_type: str                       # "upload", "resource", "project_document" (other bricks)…

    @abstractmethod
    def fetch_file(self, source_id: str | None, source_metadata: dict) -> SourceFetchResult:
        """Fetch a fresh local copy of the document (filename + temp path + version marker).
        Called at add time and at refresh/sync time — NEVER at index time (indexing reads
        the stored snapshot). Format conversions happen here (e.g. RichText JSON → md)."""

    @abstractmethod
    def get_version_marker(self, source_id: str | None, source_metadata: dict) -> str | None:
        """Cheap staleness check (e.g. last_modified_at) — None = source gone/unavailable."""

    def get_open_action(self, file: RagDatasetFileDTO) -> SourceOpenAction | None:
        """How the chat UI opens this document (url | download | none). Default: download snapshot."""

    def list_documents(self, sync_config: dict) -> list[SourceDocumentCandidate]:
        """Optional: enumerate documents for bulk sync (default: not supported)."""

    @classmethod
    def register(cls) -> None: ...         # registry keyed by source_type

class RagDocumentSourceRegistry:
    get(source_type) -> RagDocumentSource  # raises clear error for unregistered types
    all() -> list[RagDocumentSource]
```

- **`upload`** (built-in): `fetch_file` is only used at add time (the uploaded bytes ARE the
  snapshot); no version marker, no sync.
- **`resource`** (⚠️ gated by the Open decision — refactor may relocate it): wraps `RagResource` —
  compatibility pre-checks, RichText JSON→markdown conversion inside `fetch_file`,
  `get_version_marker` = `resource_model.last_modified_at`, `get_open_action` = share-link redirect,
  `list_documents` = the tag search (§6).
- **Other apps (e.g. gws_project)**: register their own provider at brick load
  (`MyDocSource.register()` in the brick's app init) — gws_ai_toolkit never imports them. This is
  the same inversion the gws_core credentials/`@credentials_type` registry uses.
- Generic compatibility check (extension in supported list, ≤15 MB) is applied by the dataset
  service on the **fetched file**, source-agnostically; providers may add stricter pre-checks.

## 2. Dependencies (constraints verified against real package metadata)

### Prerequisite: bump `openai` in gws_core

`pydantic-ai-slim[openai]` 2.x requires `openai>=2.45.0` (1.35+ requires `>=2.11`), but gws_core pins
`openai 2.2.0` — a verified conflict. **Decision: bump `openai` to `>=2.45` (latest 2.x) in
`bricks/gws_core/settings.json` first** (same major version; run the gws_core OpenAI-dependent tests
— AiExpert uses the Responses API — to confirm), released before or together with this work. This
unblocks current pydantic-ai 2.x.

### Edit `bricks/gws_ai_toolkit/settings.json`

Bump `"version"` to `0.5.0`, bump the `gws_core` brick dependency to the release carrying the openai
bump, and append to `environment.pip[0].packages` (latest-stable versions verified on PyPI at
planning time, July 2026):

```json
{ "name": "llama-index-core",                  "version": "0.14.23" },
{ "name": "llama-index-vector-stores-lancedb", "version": "0.5.0" },
{ "name": "lancedb",                           "version": "0.34.0" },
{ "name": "llama-index-embeddings-openai",     "version": "0.6.0" },
{ "name": "llama-index-readers-file",          "version": "0.6.0" },
{ "name": "docx2txt",                          "version": "0.9" },
{ "name": "pydantic-ai-slim[openai]",          "version": "2.17.0" }
```

Verified compatibility (from wheel metadata):

- All three llama-index integration packages require `llama-index-core>=0.13,<0.15` → core pinned
  0.14.23 ✔
- `lancedb 0.34.0`: `pyarrow>=16` (gws_core has 24.0.0 ✔), `pydantic>=1.10` ✔
- `llama-index-embeddings-openai 0.6.0`: `openai>=1.1.0` ✔; `llama-index-readers-file 0.6.0`:
  `pandas<3` (2.3.3 ✔), `beautifulsoup4` ✔, pulls `pypdf 6.x`
- `pydantic-ai-slim 2.17.0`: `pydantic>=2.12` (2.12.5 ✔), `openai>=2.45.0` (needs the gws_core bump
  above)
- `llama-index-vector-stores-lancedb` also pulls `pylance` + `tantivy` (Rust wheels, sizeable
  install — acceptable)

Notes:

- Do NOT add the `llama-index` meta package; core + the three integrations is the minimal set.
- `lancedb` pinned explicitly (even though pulled transitively) so upgrades are deliberate.
- `docx2txt` is a runtime requirement of `DocxReader` — declared explicitly.
- `pydantic-ai-slim[openai]` avoids installing every provider SDK; add the `anthropic` extra later
  if profiles need it.

## 3. Data model — new package `src/gws_ai_toolkit/models/rag_dataset/`

Same conventions as `models/chat/`: each model subclasses `gws_core.Model`, binds
`Meta.database = AiToolkitDbManager.get_instance().db`,
`db_manager = AiToolkitDbManager.get_instance()`, `is_table = True` (tables auto-created at brick
load — no create-table migration needed, same as the chat tables). Add
`ChatConversationMode.EMBEDDED_RAG = "embedded_rag"` (fits the 20-char `mode` column).

### Entity relationships

```
RagDataset ──< RagDatasetFile            one dataset = N indexed files
    ▲                └── row id == chunk-metadata `document_id` in LanceDB
    │ (dataset_ids JSON list — soft M2M)
RagChatProfile                           a configured chat bound to N datasets
    │ (chat_configuration["chat_profile_id"])
ChatConversation ──< ChatMessageModel ──< ChatMessageSourceModel     (EXISTING — reused)
```

The LanceDB side is schema-less from the DB's point of view: each chunk row carries metadata
`{dataset_id, document_id, filename}`; `RagDataset.id` and `RagDatasetFile.id` are the join keys
between SQL and the vector store.

### `RagDataset` — table `gws_ai_toolkit_rag_dataset`

| column | type | notes |
|---|---|---|
| id / created_at / last_modified_at | (inherited from `gws_core.Model`) | id = 36-char uuid PK |
| name | `CharField(max_length=100, unique=True)` | |
| description | `TextField(default="")` | |
| chunk_size | `IntegerField(default=1024)` | SentenceSplitter param, per dataset |
| chunk_overlap | `IntegerField(default=100)` | |
| sync_source_type | `CharField(max_length=50, null=True)` | provider used for bulk sync (§6); null = no sync |
| sync_config | `JSONField(null=True)` | provider-specific sync scope (resource provider: `{"tag_key":..., "tag_value":...}`) |

Methods: `to_dto() -> RagDatasetDTO`; `files` backref from RagDatasetFile.

### `RagDatasetFile` — table `gws_ai_toolkit_rag_dataset_file`

| column | type | notes |
|---|---|---|
| dataset | `ForeignKeyField(RagDataset, backref="files", on_delete="CASCADE")` | |
| source_type | `CharField(max_length=50)` | open provider key: `"upload"`, `"resource"`, `"project_document"`… (NOT an enum — any registered `RagDocumentSource`) |
| source_id | `CharField(max_length=100, null=True)` | opaque id in the source system (resource id, project doc id…); null for uploads |
| source_metadata | `JSONField(null=True)` | provider-specific extras |
| source_version | `CharField(max_length=100, null=True)` | provider version marker at snapshot time (staleness check for sync) |
| snapshot_path | `CharField(max_length=512)` | local snapshot in the brick filestore — ALWAYS set, whatever the origin; indexing reads only this |
| filename | `CharField(max_length=255)` | display name; shown in source pills |
| size | `BigIntegerField(default=0)` | bytes (of the snapshot) |
| index_status | `CharField(max_length=20, default="pending")` | `pending` \| `indexing` \| `done` \| `error` |
| error_message | `TextField(null=True)` | set when `index_status == "error"` |
| chunk_count | `IntegerField(default=0)` | filled after indexing (UI status) |
| indexed_at | `DateTimeField(null=True)` | when the snapshot was last indexed |

**The row id is the `document_id` written into every chunk's LanceDB metadata** —
`engine.delete_document(file.id)` and source-pill resolution both key on it. **Snapshot-on-add
invariant**: `snapshot_path` is populated for every row at add time via `provider.fetch_file(...)`;
indexing/re-indexing never contacts the source system, so a deleted resource or unavailable app never
breaks retrieval or re-index (refresh from source is a separate, explicit sync action).

### `RagChatProfile` — table `gws_ai_toolkit_rag_chat_profile`

| column | type | notes |
|---|---|---|
| name | `CharField(max_length=100, unique=True)` | |
| system_prompt | `TextField(default=<instructs tool use + answer in user's language>)` | |
| model | `CharField(max_length=100, default="openai:gpt-4.1-mini")` | pydantic-ai `provider:model` string (aligned with the gws_core agent plan) |
| top_k | `IntegerField(default=5)` | retrieval top-k |
| score_threshold | `FloatField(null=True)` | optional similarity cutoff |
| dataset_ids | `JSONField(default=list)` | bound dataset ids — **this field becomes the LanceDB `MetadataFilters` at query time** (the chat→datasets articulation from the rationale doc). Soft M2M: service validates ids on save and drops dangling ids at query time; a join table is a documented follow-up |

### Reused as-is (no schema change)

`ChatConversation` (stores `{"chat_profile_id": ...}` in its `configuration` JSON,
`mode="embedded_rag"`, `external_conversation_id` unused), `ChatMessageModel`,
`ChatMessageSourceModel` (persists the `RagChatSource` DTOs the new stack emits), `ChatApp`, `User`.

### Non-DB entities (module DTOs, `rag/embedded/`)

- `EmbeddingConfig` (provider `"openai"|"mock"`, model, api_key, dimensions) and `ChunkConfig`
  (chunk_size, chunk_overlap) — `BaseModelDTO`s configuring the engine.
- `RetrievedChunk` (chunk_id, content, score, dataset_id, document_id, filename) — retrieval result;
  `.to_rag_chat_source()` maps to the existing `RagChatSource`/`RagChatSourceChunk` DTOs.
- `RagDatasetDTO` / `RagDatasetFileDTO` / `RagChatProfileDTO` (+ `Save*` input DTOs) in
  `rag_dataset_dto.py` — Reflex states consume DTOs, never Peewee rows (existing convention).
- `SyncReport` (added / updated / removed / skipped lists) — result of a provider sync run (§6);
  `SourceFetchResult`, `SourceDocumentCandidate`, `SourceOpenAction` — provider-contract DTOs (§1).

### Services

- **`RagDatasetService`** (mutations under `@AiToolkitDbManager.transaction()`; fully
  source-agnostic — talks only to the `RagDocumentSource` registry):
  - dataset CRUD;
  - `add_uploaded_document(dataset_id, filename, bytes)` — convenience wrapper: writes the snapshot,
    creates the row with `source_type="upload"`, status `pending`;
  - `add_document(dataset_id, source_type, source_id, source_metadata)` — generic path:
    `provider.fetch_file(...)` → generic compatibility check (ext/size on the fetched file) → copy
    to snapshot path → row with `source_version`, status `pending`;
  - `refresh_document(file_id)` — re-fetch from provider, replace snapshot, update `source_version`,
    status `pending`;
  - `index_file(file_id, engine)` — status transitions; reads ONLY `snapshot_path` (no source
    access);
  - `reindex_file`; `delete_file` (chunks + snapshot + row); `delete_dataset` (chunks + files dir +
    rows via CASCADE);
  - `sync_documents(dataset_id, engine) -> SyncReport` — provider-driven bulk sync (§6).
- **`RagChatProfileService`**: CRUD + `get_valid_dataset_ids(profile)`.

## 4. Chat loop — `models/chat/conversation/embedded_rag_chat_conversation.py`

`EmbeddedRagChatConversation(BaseChatConversation[ChatUserMessageText])`, mode `embedded_rag`,
`chat_configuration={"chat_profile_id": ...}` for restore.

- pydantic-ai `Agent(model=profile.model, instructions=profile.system_prompt,
  deps_type=RetrievalDeps)`; provider key injected explicitly via
  `OpenAIChatModel(name, provider=OpenAIProvider(api_key=...))` (no process-env reliance).
- `@agent.tool search_knowledge(ctx, query)` → `engine.retrieve(query, dataset_ids, top_k,
  score_threshold)`; appends chunks to `deps.collected_chunks`; returns formatted passages.
- `_call_ai_chat`: yield user message → stream text deltas as
  `build_current_message(delta, append=True)` → on completion
  `close_current_message(sources=deduped [c.to_rag_chat_source()])` (→ `ChatMessageSource`,
  persisted by existing models); errors → `ChatMessageError`.
- **Async→sync bridge — settled**: `agent.run_stream_sync(...)` exists in pydantic-ai 2.17.0
  (verified in the wheel) — iterate `stream_text(delta=True)` from the sync generator; no adapter
  needed.
- History: in-memory `list[ModelMessage]` per session, extended with `result.new_messages()`; on
  restore, rebuilt from persisted messages (user→UserPromptPart, assistant→TextPart; tool turns not
  persisted — accepted V1).
- Agent-building overridable for tests (`TestModel`/`FunctionModel`, no API calls).

## 5. Reflex UI — new folder `apps/rag_app/_rag_app/rag_app/reflex/embedded_rag/`

Follows the existing component/state folder convention (relative imports, default button colors, red
for destructive).

- `core/embedded_rag_app_state.py` — shared helpers (build default engine, resolve API key from
  params, `enable_embedded_rag` feature flag).
- `datasets/` — dataset list (+create/delete), dataset detail (file table with source-type chip,
  status chip, chunk_count, error tooltip, re-index/refresh/delete per file, "Sync now" button when a
  sync source is configured), upload component (`rx.upload.root` + `rx.upload_files`, pattern from
  `ai_table_standalone_app` home_page.py; background event indexes pending files), add-document
  dialog (source-type select from `RagDocumentSourceRegistry.all()`; the resource provider
  contributes a resource-search picker with compatibility feedback — other providers bring their own
  picker or a plain source-id field).
- `chats/` — chat-profile list + edit (prompt textarea, model select, top_k, threshold, dataset
  multi-checkbox).
- `chat/` — `EmbeddedRagChatState(ConversationChatStateBase)`:
  `_create_conversation`/`_restore_conversation` mirror `RagChatState` (profile id from conversation
  `configuration`); `_after_conversation_updated` → history refresh +
  `replaceState /rag/chat/<id>`; **override `open_document`/`open_ai_expert`** (resolve
  `RagDatasetFile` → delegate to `provider.get_open_action(file)`: resource provider → share-link
  redirect, default → `rx.download` of the snapshot; AI Expert hidden for embedded sources in V1).
  Header: profile selector. Reuses `chat_base` widget + `rag_page_layout_component` + history
  sidebar.

**Routes added to `rag_app.py`** (old routes untouched, coexistence via `enable_embedded_rag` launch
param): `/rag`, `/rag/chat/[conversation_id]`, `/rag/datasets`, `/rag/datasets/[dataset_id]`,
`/rag/chats`. Extend the history sidebar's mode→route mapping for `embedded_rag`. Add params to
`dev_config.json` (`enable_embedded_rag`, optional `openai_credentials_name`).

**Generator task**: `apps/rag_app/generate_embedded_rag_app.py` — `GenerateEmbeddedRagApp(Task)`
modeled on `GenerateDatahubRagFlowApp` (chat_app_name, optional
`CredentialsParam(CredentialsDataOther)`, admin-history/auth flags). Re-export in `_app/ai_rag`
facade if full_app should pick it up (check at implementation).

## 6. Bulk sync — provider-driven (no `BaseRagService`, no resource coupling)

> ⚠️ The generic algorithm below is settled; the **resource-provider specifics are gated by the Open
> decision** (global data lab refactor) — see the top of this document.

Sync state lives in `RagDatasetFile` rows (`source_id` + `source_version`), never in the source
system. Generic algorithm in `RagDatasetService.sync_documents(dataset_id, engine)`, valid for ANY
provider implementing `list_documents`:

1. `provider = registry.get(dataset.sync_source_type)`;
   `candidates = provider.list_documents(dataset.sync_config)`.
2. Per candidate: skip incompatible; **new** `source_id` → `add_document(...)` (snapshot + index);
   **known** and `candidate.version_marker != file.source_version` → `refresh_document` + re-index;
   unchanged → skip.
3. Dataset files of this `source_type` whose `source_id` is no longer in `candidates` → delete
   (chunks + snapshot + row).
4. Return `SyncReport` (added/updated/removed/skipped) → toast/dialog.

The **resource provider's** `list_documents` implements the tag search (`ResourceSearchBuilder`
query copied from `TagRagAppService`: tag filter + fs-node + not-archived), with
`version_marker = last_modified_at`. A future gws_project provider implements its own enumeration;
nothing in this brick changes. Manually added documents (uploads, single adds) are never touched by
sync.

Legacy `rag_document`/`rag_dataset_id`/`rag_sync` tags are deliberately not written (no interference
with Dify/RagFlow pages).

## 7. Disk layout

`<brick_extension_dir>/gws_ai_toolkit/embedded_rag/lancedb/` (default instance) and
`.../embedded_rag/files/<dataset_id>/<file_id>_<sanitized_filename>` — **snapshots of ALL documents**
(uploads and fetched source docs alike). The snapshot is the single indexing input and the fallback
`open_document` target (download); the source system is only contacted at add/refresh/sync time.
Per-lab follow-up = `embedded_rag/instances/<scope>/lancedb` passed to the constructor — documented
in `embedded_rag_storage.py`, not built.

## 8. Verification

Tests in `tests/test_gws_ai_toolkit/` (run: `cd bricks/gws_ai_toolkit && gws server test <file>`;
fixtures under `tests/testdata/embedded_rag/`):

1. `test_embedded_rag_engine.py` — mock embedding; index md/txt/csv/richtext-json; **dataset
   metadata-filter isolation** (dataset A query never returns B); delete_document scoping; re-index
   idempotency; score threshold; FR-over-EN case skip-unless `OPENAI_API_KEY`.
2. `test_rag_dataset_service.py` — temp engine dir; upload/index status transitions incl. error
   path; delete cleanup (chunks + snapshot); profile CRUD + dangling ids; **source registry**: a
   test-only `FakeDocumentSource` registered in the test proves
   `add_document`/`refresh_document`/`sync_documents` work against an unknown provider (the
   gws_project scenario); snapshot invariant (index works after the fake source "disappears").
3. `test_embedded_rag_chat_conversation.py` — `store_conversation_in_db=False`,
   `TestModel`/`FunctionModel` forcing a `search_knowledge` call; assert yield sequence user →
   streaming* → `ChatMessageSource` with sources; error path.
4. Manual: `gws reflex run .../rag_app/_rag_app/dev_config.json`,
   `xvfb-run python take_screenshot.py --route /rag/datasets|/rag/chats|/rag`; full loop: create
   dataset → upload md → done → create profile → chat → source pill → reload `/rag/chat/<id>`. Run
   `ruff check --fix` on modified files.

## 9. Implementation order (each step verifiable)

0. **gws_core openai bump** — `openai` → latest 2.x in `bricks/gws_core/settings.json`, run
   gws_core's OpenAI-dependent tests, release (or coordinate a joint release).
1. **Deps + engine** — settings.json, install (settles the remaining LanceDB delete-predicate
   unknown), `rag/embedded/`, engine tests green.
2. **Models + services** — `models/rag_dataset/`, `EMBEDDED_RAG` mode, service tests green (incl.
   the source-registry `FakeDocumentSource` tests + upload provider — these don't depend on the open
   decision).
3. **Chat loop** — conversation class, credentials helper, conversation tests green.
4. **UI: dataset manager** — routes + feature flag, upload+index end-to-end in dev app.
5. **UI: chat profiles + chat window** — full manual chat loop with restore.
6. **External-document providers + sync** — ⚠️ **gated by the Open decision above** (global data lab
   refactor). Once settled: `resource` provider (or its post-refactor equivalent, possibly registered
   by `gws_workflow`), generic `sync_documents`, dataset-detail sync UI + add-document dialog; verify
   with a tagged lab resource: sync → query → modify → re-sync updates.
7. **Packaging + docs** — generator task, facade exports, update brick CLAUDE.md routes; both plan
   docs → `docs/done/` on completion. Full test suite.

## Risks (explicit)

Settled during planning (verified against package metadata / code):

- ~~pydantic-ai sync streaming~~ — `run_stream_sync` exists in 2.17.0.
- ~~pip resolution~~ — all llama-index/lancedb constraints compatible with gws_core pins; the one
  real conflict (openai) resolved by the gws_core bump (step 0).
- ~~JSONField availability~~ — `gws_core.JSONField` already used by the chat models.

Remaining:

- **LanceDB metadata layout / delete-predicate syntax** (flat columns vs struct) — pinned by step-1
  tests, encapsulated in `_delete_where()`.
- **Multi-process access to the LanceDB dir**: the Reflex app runs as its own process; gws Tasks
  (generator task, future indexing Task) run in the server process. LanceDB handles concurrent
  readers, but V1 enforces a **single-writer rule**: all writes (indexing/deletes) happen in the
  Reflex app process only — documented in `embedded_rag_engine.py`.
- **Engine handle in Reflex state**: don't store a live `EmbeddedRagEngine`/LanceDB connection on
  state or conversation objects across events (picklability); build the engine lazily per operation
  (cheap: `lancedb.connect` on a local dir).
- Synchronous indexing/streaming inside Reflex background events (accepted existing pattern; long
  "indexing" status acceptable V1; task queue = follow-up).
- `dataset_ids` JSONField has no FK integrity (service-side validation; M2M follow-up).
- openai bump in gws_core could affect its existing OpenAI code paths (AiExpert Responses API) —
  covered by running gws_core tests at step 0.
- **Snapshot trade-offs** (accepted by design): storage duplication (≤15 MB/doc cap keeps it cheap)
  and staleness — a snapshot only updates on explicit refresh/sync, never silently tracks the
  source. This is the price of indexing/retrieval never depending on source availability.

## Critical files

- `src/gws_ai_toolkit/models/chat/conversation/base_chat_conversation.py` — the seam (generator
  contract, persistence helpers)
- `src/gws_ai_toolkit/apps/rag_app/_rag_app/rag_app/reflex/chat_base/conversation_chat_state_base.py`
  — state base hooks
- `src/gws_ai_toolkit/apps/rag_app/_rag_app/rag_app/reflex/rag_chat/rag_chat_state.py` — reference
  for the new chat state
- `src/gws_ai_toolkit/rag/common/rag_resource.py` — compatibility rules + RichText→markdown reuse
- `settings.json` — dependency gate (step 1)
