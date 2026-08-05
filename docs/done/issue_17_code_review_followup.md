# Code review follow-up — issue #17 (resource provider + import by tag)

Two-axis review (Standards / Spec) of commit `6b9996b` **(feat)[KnowledgeBase] resource provider and
import by tag**, run 2026-08-04.

**Update 2026-08-05: the five-item fix list below has been applied** in a follow-up commit. The
"Deliberate, would keep" and "Scope-creep" sections stand as recorded. "Still unverified" (the UI
click-through) remains open.

## How to pick this back up

```bash
cd /lab/user/bricks/gws_ai_toolkit

git diff 6e84727...HEAD                     # the reviewed diff (13 files, ~1630 insertions)
git show --stat 6b9996b                     # what it touched

gws server test test_knowledge_base_resource_source test_knowledge_base_service --parallel
gws reflex compile src/gws_ai_toolkit/apps/rag_app/_rag_app/dev_config.json
```

Fixed point was `6e84727` (the commit's parent), so the diff is exactly this one commit.

Pre-existing suite failures, unrelated to this work and confirmed present without it: the
`test_ai_table_stats_tests*` posthoc tests, `test_analytics_resource_action_plugin`, and
`test_rag_chat_conversation` (needs `RAGFLOW_API_KEY` / `RAGFLOW_BASE_URL`).

## The fix list (agreed, not yet applied)

Five items, all in code added by this commit. Suggested as one follow-up commit.

### 1. `import_by_tag` is annotated as an async generator but never yields — HARD

`.../knowledge_base/knowledge_bases/add_document_dialog/add_document_dialog_state.py:345`

```python
@rx.event(background=True)
async def import_by_tag(self) -> AsyncGenerator[rx.event.EventType, None]:
```

It contains no `yield` — the annotation was copied from `add_from_source` (line 299) and
`handle_upload` (line 238), which do yield. Change to `-> None`. Violates PY-TYPE-001.

Worth deciding at the same time: the handler currently reports success only by opening the report
dialog. If a toast is wanted too, it becomes a real generator and the annotation stands — but then
re-check the "never `yield SiblingState.event` from a background handler" rule (a `rx.toast` is
fine, a sibling state's event is not).

### 2. `open_dialog` does not reset the tag fields — PARTIAL (Spec)

`add_document_dialog_state.py:161-175` resets `source_id`, `source_metadata_json` and `rejections`,
but not `tag_key`, `tag_value` or `add_mode`. Reopening the dialog therefore pre-fills the previous
criterion, against this file's own stated rule that "what is on screen always belongs to the attempt
the user just made". Add the three resets.

Judgement call while you are there: pre-filling the last tag may actually be *wanted* for a repeated
import. If so, keep the values and say so in the docstring — the point is that it should be a
decision, not an oversight.

### 3. `known_source_ids` is not scoped to the source type being imported — LOOKS WRONG (Spec)

`src/gws_ai_toolkit/models/knowledge_base/knowledge_base_service.py:365`

```python
known_source_ids = {
    document.source_id
    for document in self.get_documents(knowledge_base.id)
    if document.source_id
}
```

Every document of the knowledge base contributes, whatever its `source_type`. A candidate whose
`source_id` happens to equal another provider's row id is then reported "already present" and never
added. Not reachable today — resource ids are UUIDs and the only other provider is `upload`, whose
`source_id` is always `None` — but it is wrong as written, and the seam exists precisely so other
bricks can register providers with id spaces of their own.

Fix: filter on `document.source_type == source_type` when building the set. The issue's wording
supports it: "Candidate whose `source_id` already has a row in this knowledge base → skip".

### 4. `imported_from` can silently overwrite a provider's own key — LOOKS WRONG (Spec)

`knowledge_base_service.py:541`

```python
return {**(candidate.source_metadata or {}), "imported_from": dict(criteria or {})}
```

A provider returning a candidate that already carries an `imported_from` key loses it with no
warning. Decide which wins and make it explicit — either keep the service's value and log when it
displaces one, or reserve the key in the `SourceDocumentCandidate` docstring so a provider knows not
to use it. (The service's value should stay authoritative; issue #27 reads it.)

### 5. Naming and duplication nits in the new code — MEDIUM

- `knowledge_base_service.py:544` — `_skipped(candidate, reason, message)` reads as a predicate but
  builds a `SkippedDocumentDTO`. Rename to `_build_skipped_document` (or similar).
- `add_document_dialog_state.py:125` — `is_tag_import_mode` repeats
  `self.selected_source_type == RESOURCE_SOURCE_TYPE` instead of reusing `supports_tag_import`
  (line 120).
- `add_document_dialog_state.py` — `import_by_tag` re-implements `_get_knowledge_base_id`
  (`get_state` → `get_loaded_knowledge_base_id()` → raise) rather than calling it. It was inlined
  because the background handler needs the detail state anyway, inside the same `async with self`;
  reuse it if that reads better.
- `tests/test_gws_ai_toolkit/test_knowledge_base_service.py:548` — `self.service._fail_indexing(...)`
  reaches into a private method. Neighbouring tests drive the service publicly; this one could too
  (index against an engine that fails, as `test_indexing_error_path_...` does by removing the
  snapshot).

## Deliberate, would keep

Recorded so a later reviewer does not re-raise them.

- **`criteria: dict` + `TAG_KEY_CRITERION` / `TAG_VALUE_CRITERION` string keys.** Reads as Primitive
  Obsession / Data Clumps, but a criterion is provider-specific by design and its keys are the shape
  stamped into `source_metadata.imported_from` — see the settled point in
  `src/gws_ai_toolkit/rag/CLAUDE.md`.
- **`reflex/knowledge_base/core/knowledge_base_errors.py` as a pure re-export**, and
  **`KnowledgeBaseDetailState.reload_documents()` as a one-line pass-through.** Both are Middle Men.
  The first keeps the app's call sites reading as app code while the list itself lives next to the
  provider seam that defines half of it; the second exists because a background handler must not
  chain a sibling event. Kept on purpose.
- **`ImportSkipReason` not being rendered by the UI** (the dialog shows `filename` + `message`). The
  enum is what lets a caller group or filter skips, and the report already carries the reason string.

## Still unverified

- **The UI half of the last acceptance criterion.** "Verified against real tagged lab resources:
  import → query → modify → refresh → query" is proven at service level against real `ResourceModel`
  File resources, real tags and real retrieval (`test_knowledge_base_resource_source.py`). The
  import-by-tag dialog, the report dialog and the shared indexing slot are only proven to *compile*
  — nobody has clicked through them in a running app.

  To close it: `gws reflex run src/gws_ai_toolkit/apps/rag_app/_rag_app/dev_config.json`, tag two or
  three real lab resources (one of them a `.csv`, so a skip appears in the report), open a knowledge
  base → **Add documents** → **Import by tag**, and check the report lists the added documents and
  the refused one with its reason, that the table refreshes without a manual reload, and that the
  "Indexing…" indicator clears afterwards. The slot handover between
  `AddDocumentDialogState.import_by_tag` and `KnowledgeBaseDetailState` is the part a compile cannot
  reach.

## Scope-creep notes (flagged, no action proposed)

Raised by the Spec axis as beyond what #17 literally asked for; all three look justified, listed in
case a reviewer disagrees.

- The shared indexing-slot API on `KnowledgeBaseDetailState` (`try_begin_indexing_run`,
  `end_indexing_run`, public `reload_documents`, `INDEXING_IN_PROGRESS_MESSAGE`) — needed because the
  import indexes as it adds and must not race the page's pending sweep.
- Moving `DOCUMENT_REJECTION_ERRORS` into `rag/knowledge_base/sources/knowledge_base_source.py` with
  a re-export shim in the app — the bulk import needs the same list as the three existing call sites,
  and two definitions would drift.
- The provider's own extension/size pre-check, where the plan says the service-level check on the
  fetched file is "unchanged". The service check *is* unchanged and still authoritative; the
  pre-check only avoids copying a 400 MB resource in order to reject it. `check_size_is_within_cap`
  was made public so both use one cap.
