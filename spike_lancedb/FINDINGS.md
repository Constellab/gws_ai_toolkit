# Spike verdicts — LanceDB hybrid search, August 2026

Primary source for the *Spike results* section of
`docs/todo/rag_embedded_stack_implementation_plan.md` (on `feature/migration`). This branch is
throwaway: it exists so the numbers below can be re-derived rather than trusted, and so the
fixtures can be lifted rather than rebuilt.

Reproduce with `./run.sh`. Deterministic — mock embedding, no API key, no network.

Environment as run: `lancedb 0.36.0`, `llama-index-core 0.14.23`, `pyarrow 24.0.0`,
`pandas 2.3.3`, `tantivy 0.26.0`, Python 3.10.12.

## Verdicts

| # | Question | Verdict |
|---|---|---|
| 1a | Does a metadata predicate push down in **hybrid** mode? | **PASS** in vector, FTS and hybrid, at both layers (raw `where(..., prefilter=True)` and llama-index `MetadataFilters`). Knowledge-base isolation holds. |
| 1b | Does a second filter narrow to one document? | **PASS** — `knowledge_base_id = 'x' AND document_id = 'y'`. AI Expert's `relevant_chunks` path is safe. |
| 2 | Delete predicate syntax | **PASS** for flat columns, `IN (...)` lists, backticked identifiers. Single quotes in values must be **doubled**: `document_id = 'doc_o''brien'`. |
| 3 | Is the FTS index incremental? | **PASS, and the plan's assumption was wrong** — rows added after index creation are immediately searchable (unindexed-fragment scan). No explicit optimise step needed. `optimize()` and `create_fts_index(replace=True)` also both work. |
| 4 | Fused score semantics | RRF `_relevance_score`, ~0.015–0.033 on this corpus. Vector mode gives `_distance`, FTS gives `_score` (BM25). **Not** interchangeable with cosine similarity. |
| 4b | Is LanceDB's "reranker" a model? | **No** — `RRFReranker` (k=60) and `LinearCombinationReranker` (weight=0.7) are pure arithmetic. The plan's "no reranker" meant no cross-encoder. |
| 5 | llama-index `MetadataFilters` in hybrid mode | **PASS** — pushes down. But see 5b. |
| 5b | Is llama-index `similarities` an absolute score? | **FAIL** — it is rank position rescaled. See below. |

## The finding that changed the design

`LanceDBVectorStore.query()` does not surface the fused score. Same query, same corpus, varying
`top_k`:

```
top_k=2  ->  [1.0, 0.0]
top_k=3  ->  [1.0, 0.5, 0.0]
top_k=4  ->  [1.0, 0.6667, 0.3333, 0.0]
top_k=6  ->  [1.0, 0.8, 0.6, 0.4, 0.2, 0.0]
```

That is `1 - i/(n-1)` — pure rank position. First is always `1.0`, last always `0.0`, evenly
spaced regardless of actual relevance. A threshold on it means "in the top slice", not "relevant
enough", and its meaning shifts with `top_k`.

Consequence, now settled in the plan: **the engine reads the LanceDB table directly** and
thresholds on `_relevance_score`. The wrapper also nests metadata under a `metadata: struct<...>`
column (schema printed by probe 5), which would force `metadata.document_id = '...'` predicates;
owning the table keeps the flat schema §7 assumes.

## What lifts out of here into real code

- `kb_probe.py` → `MockEmbedding` is what `EmbeddingFactory`'s `"mock"` provider needs: deterministic
  hashed bag-of-words, 64 dims, L2-normalised, no API key.
- `kb_probe.py` → `build_corpus()` is the fixture for `test_knowledge_base_engine.py`: two knowledge
  bases, two documents each, with `CANARY_TERM` present in **only one document of one knowledge
  base**. That shape is what makes the isolation test and the `document_ids` test sharp rather than
  vacuous — a corpus where every knowledge base mentions everything proves nothing.
- The isolation assertion itself (probe 1a) should survive as a regression test: a lancedb upgrade
  could regress push-down, and it would fail silently as cross-knowledge-base leakage.

## Untested

- Delete-by-predicate against the wrapper's **nested** `metadata` struct — only matters if the
  wrapper is kept, and the 5b finding says it should not be.
- `llama-index-readers-file` and `llama-index-embeddings-openai` were never installed, so their
  pins are still unverified (see §8 of the plan).
- Scale. Six rows. Nothing here says anything about FTS cost as the unindexed tail grows.
