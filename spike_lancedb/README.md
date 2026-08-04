# PROTOTYPE — LanceDB hybrid-search spike (wipe me)

Throwaway. Answers step-1 questions from
`bricks/gws_ai_toolkit/docs/todo/rag_embedded_stack_implementation_plan.md`.
Nothing here ships. The findings go back into that doc; this code does not.

## The question

The plan builds a knowledge-base engine on LlamaIndex + LanceDB where **several knowledge
bases share one LanceDB table, separated only by a metadata filter**. Retrieval is hybrid
(vector + full-text, model-free fusion). Four things must be true for that design to hold,
and none can be settled on paper:

1. **Does `MetadataFilters` push down in hybrid mode?** This is the *isolation mechanism
   between knowledge bases* — if it does not push down, a query on knowledge base A can
   return B's chunks. A correctness bug, not a performance one. Includes the second filter
   on the same path (`document_ids`), which AI Expert's `relevant_chunks` mode needs.
2. **What is the delete predicate syntax?** Flat column vs nested `metadata` struct — the
   thing `_delete_where` is meant to encapsulate.
3. **Is the FTS index incremental?** If rows added after index creation are invisible to
   full-text search, the write path needs an explicit optimise/rebuild step.
4. **What are the fused score semantics?** `RagChatProfile.score_threshold` is currently
   specified as a cosine-similarity threshold. An RRF score is not a cosine similarity.

## Run

```bash
./run.sh
```

First run creates `.venv/` (with `--system-site-packages`, so it inherits gws_core's
pyarrow/pandas) and installs lancedb + llama-index. Later runs reuse it.

The probe uses a **deterministic hashed bag-of-words mock embedding** — no OpenAI key, no
network, no cost. Data lives in `./scratch_db/`, recreated on every run.

## Reading the output

Each probe prints `PASS` / `FAIL` / `INFO` and the evidence behind it. `FAIL` on probe 1 is
the one that changes the plan.
