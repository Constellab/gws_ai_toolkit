"""PROTOTYPE — LanceDB hybrid-search probe runner (wipe me).

Answers the four step-1 questions in
bricks/gws_ai_toolkit/docs/todo/rag_embedded_stack_implementation_plan.md.

Deviates from the usual logic-prototype shape (interactive TUI) on purpose: there is no
state machine to drive here. The questions are "does this library actually do X", so the
right artifact is a deterministic probe that prints a verdict per question. Run it, read
the verdicts.

Two layers are probed separately, because they can disagree and the difference decides
the design:

  Layer A — raw lancedb          does the capability exist at all?
  Layer B — llama-index wrapper  does the layer the plan is built on expose it?

If A passes and B fails, the answer is "reach through the wrapper", not "drop hybrid".
"""

from __future__ import annotations

import shutil
import traceback
from pathlib import Path

import pyarrow as pa

from kb_probe import CANARY_TERM, DIMENSIONS, Chunk, MockEmbedding, build_corpus

DB_DIR = Path(__file__).parent / "scratch_db"

BOLD = "\x1b[1m"
DIM = "\x1b[2m"
GREEN = "\x1b[32m"
RED = "\x1b[31m"
YELLOW = "\x1b[33m"
RESET = "\x1b[0m"

EMBEDDING = MockEmbedding()


# --------------------------------------------------------------------------------------
# output helpers
# --------------------------------------------------------------------------------------

def question(number: str, text: str) -> None:
    print(f"\n{BOLD}{'=' * 86}{RESET}")
    print(f"{BOLD}Q{number}. {text}{RESET}")
    print(f"{BOLD}{'=' * 86}{RESET}")


def verdict(state: str, text: str) -> None:
    colour = {"PASS": GREEN, "FAIL": RED, "INFO": YELLOW, "ERROR": RED}[state]
    print(f"  {colour}{BOLD}{state}{RESET}  {text}")


def detail(text: str) -> None:
    print(f"        {DIM}{text}{RESET}")


def show_hits(hits: list[dict], score_keys: tuple[str, ...]) -> None:
    if not hits:
        detail("(no rows returned)")
        return
    for hit in hits:
        scores = " ".join(
            f"{key}={hit[key]:.4f}" for key in score_keys if isinstance(hit.get(key), float)
        )
        detail(f"{hit.get('knowledge_base_id')}/{hit.get('document_id')} "
               f"{hit.get('chunk_id')}  {scores}")


# --------------------------------------------------------------------------------------
# Layer A — raw lancedb
# --------------------------------------------------------------------------------------

def arrow_schema() -> pa.Schema:
    """Flat columns, as the plan's chunk metadata describes them."""
    return pa.schema([
        pa.field("vector", pa.list_(pa.float32(), DIMENSIONS)),
        pa.field("chunk_id", pa.string()),
        pa.field("text", pa.string()),
        pa.field("knowledge_base_id", pa.string()),
        pa.field("document_id", pa.string()),
        pa.field("filename", pa.string()),
        pa.field("access_scope", pa.string()),
    ])


def to_row(chunk: Chunk) -> dict:
    return {
        "vector": EMBEDDING.embed(chunk.content),
        "chunk_id": chunk.chunk_id,
        "text": chunk.content,
        "knowledge_base_id": chunk.knowledge_base_id,
        "document_id": chunk.document_id,
        "filename": chunk.filename,
        "access_scope": chunk.access_scope,
    }


def create_fts_index(table, column: str = "text") -> str:
    """Returns a description of how the index was created — the flavour matters for Q3
    (tantivy indexes and native indexes have different incrementality behaviour).
    """
    try:
        table.create_fts_index(column, replace=True, use_tantivy=False)
        return "native (use_tantivy=False)"
    except TypeError:
        table.create_fts_index(column, replace=True)
        return "default flavour (use_tantivy not accepted)"


def search_raw(table, mode: str, query_text: str, where: str | None, limit: int = 6) -> list[dict]:
    """One search across all three modes, with an optional pushed-down predicate."""
    query_vector = EMBEDDING.embed(query_text)

    if mode == "vector":
        builder = table.search(query_vector, vector_column_name="vector")
    elif mode == "fts":
        builder = table.search(query_text, query_type="fts")
    elif mode == "hybrid":
        builder = table.search(query_type="hybrid", vector_column_name="vector")
        builder = builder.vector(query_vector).text(query_text)
    else:
        raise ValueError(mode)

    if where is not None:
        try:
            builder = builder.where(where, prefilter=True)
        except TypeError:
            # Older/newer signatures drop the prefilter kwarg.
            builder = builder.where(where)

    return builder.limit(limit).to_list()


def probe_raw_isolation(table) -> None:
    question("1a", "Raw lancedb: does a metadata predicate push down in HYBRID mode? "
                   "(knowledge-base isolation)")

    for mode in ("vector", "fts", "hybrid"):
        print(f"\n  {BOLD}mode = {mode}{RESET}")
        try:
            unfiltered = search_raw(table, mode, CANARY_TERM, where=None)
        except Exception as error:
            verdict("ERROR", f"unfiltered {mode} search raised {type(error).__name__}: {error}")
            detail(traceback.format_exc().strip().splitlines()[-1])
            continue

        detail("unfiltered — establishing that the canary is reachable at all:")
        show_hits(unfiltered, ("_distance", "_score", "_relevance_score"))
        canary_reachable = any(hit["knowledge_base_id"] == "kb_b" for hit in unfiltered)
        if not canary_reachable:
            verdict("INFO", "canary term did not surface unfiltered — this mode's recall is the "
                            "finding, the isolation test below is weaker than intended")

        try:
            filtered = search_raw(table, mode, CANARY_TERM, where="knowledge_base_id = 'kb_a'")
        except Exception as error:
            verdict("ERROR", f"filtered {mode} search raised {type(error).__name__}: {error}")
            detail("a predicate that RAISES in hybrid mode is a different (better) problem "
                   "than one that is silently ignored")
            continue

        detail("filtered to knowledge_base_id = 'kb_a':")
        show_hits(filtered, ("_distance", "_score", "_relevance_score"))

        leaked = [hit for hit in filtered if hit["knowledge_base_id"] != "kb_a"]
        if leaked:
            verdict("FAIL", f"{len(leaked)} row(s) from another knowledge base leaked through "
                            f"the filter in {mode} mode")
            detail("this is the correctness bug the plan flags as highest severity")
        else:
            verdict("PASS", f"filter pushed down in {mode} mode — no cross-knowledge-base leak")


def probe_raw_document_filter(table) -> None:
    question("1b", "Raw lancedb: does a SECOND filter narrow to one document? "
                   "(AI Expert's relevant_chunks path)")

    predicate = "knowledge_base_id = 'kb_b' AND document_id = 'doc_b1'"
    try:
        hits = search_raw(table, "hybrid", CANARY_TERM, where=predicate)
    except Exception as error:
        verdict("ERROR", f"{type(error).__name__}: {error}")
        return

    show_hits(hits, ("_relevance_score",))
    wrong = [hit for hit in hits if hit["document_id"] != "doc_b1"]
    if wrong:
        verdict("FAIL", f"{len(wrong)} row(s) from outside doc_b1 — document_ids cannot be "
                        f"implemented as a pushed-down filter")
    elif not hits:
        verdict("INFO", "no rows at all — filter applied but recall is zero, investigate")
    else:
        verdict("PASS", "document_ids narrows within a knowledge base on the same push-down path")


def probe_delete_predicate(db) -> None:
    question("2", "Raw lancedb: delete predicate syntax and quote escaping "
                  "(what _delete_where must encapsulate)")

    table = db.create_table("delete_probe", schema=arrow_schema(), mode="overwrite")
    table.add([to_row(chunk) for chunk in build_corpus()])
    tricky = Chunk("q1", "A chunk from O'Brien's report.", "kb_a", "doc_o'brien", "o'brien.md")
    table.add([to_row(tricky)])

    detail(f"rows before: {table.count_rows()}")

    for label, predicate in (
        ("flat column, single quotes", "document_id = 'doc_a1'"),
        ("IN list", "document_id IN ('doc_a2')"),
        ("backticked column", "`document_id` = 'doc_b1'"),
        ("value containing a quote (doubled)", "document_id = 'doc_o''brien'"),
    ):
        before = table.count_rows()
        try:
            table.delete(predicate)
            after = table.count_rows()
            if after < before:
                verdict("PASS", f"{label}: {predicate}")
                detail(f"deleted {before - after} row(s)")
            else:
                verdict("FAIL", f"{label}: accepted but deleted nothing — {predicate}")
                detail("a silently-matching-nothing delete is the dangerous case: re-index "
                       "would duplicate chunks instead of replacing them")
        except Exception as error:
            verdict("ERROR", f"{label}: {type(error).__name__}: {error}")

    detail(f"rows after: {table.count_rows()}")


def probe_fts_incrementality(db) -> None:
    question("3", "Raw lancedb: is the FTS index incremental? "
                  "(does the write path need an explicit optimise step?)")

    table = db.create_table("fts_probe", schema=arrow_schema(), mode="overwrite")
    table.add([to_row(chunk) for chunk in build_corpus()])
    flavour = create_fts_index(table)
    detail(f"FTS index flavour: {flavour}")

    new_term = "ZZQUUX-4242"
    table.add([to_row(Chunk("new1", f"A freshly added chunk mentioning {new_term}.",
                            "kb_a", "doc_new", "new.md"))])
    detail(f"added one row containing {new_term} AFTER the index was built")

    def find_new_term() -> int:
        try:
            return len(table.search(new_term, query_type="fts").limit(5).to_list())
        except Exception as error:
            verdict("ERROR", f"fts search raised {type(error).__name__}: {error}")
            return -1

    found_before = find_new_term()
    if found_before > 0:
        verdict("PASS", "new row is full-text searchable with no explicit index maintenance")
        detail("lancedb is scanning the unindexed fragment for us — cheap now, but confirm "
               "it stays cheap as the unindexed tail grows")
    elif found_before == 0:
        verdict("FAIL", "new row is INVISIBLE to full-text search until the index is rebuilt")
        detail("the plan's write path needs an explicit optimise/reindex step, and every "
               "just-indexed document is missing from FTS until it runs")

    for label, action in (
        ("table.optimize()", lambda: table.optimize()),
        ("create_fts_index(replace=True)", lambda: create_fts_index(table)),
    ):
        try:
            action()
        except Exception as error:
            verdict("INFO", f"{label} unavailable: {type(error).__name__}: {error}")
            continue
        found_after = find_new_term()
        state = "PASS" if found_after > 0 else "FAIL"
        verdict(state, f"after {label}: new term {'found' if found_after > 0 else 'STILL missing'}")


def probe_score_semantics(table) -> None:
    question("4", "Raw lancedb: what do the scores mean per mode? "
                  "(RagChatProfile.score_threshold is specified as a cosine threshold)")

    for mode, keys in (
        ("vector", ("_distance",)),
        ("fts", ("_score",)),
        ("hybrid", ("_relevance_score", "_distance", "_score")),
    ):
        try:
            hits = search_raw(table, mode, "ingestion worker object store", where=None, limit=4)
        except Exception as error:
            verdict("ERROR", f"{mode}: {type(error).__name__}: {error}")
            continue
        present = sorted(key for key in hits[0].keys() if key.startswith("_")) if hits else []
        verdict("INFO", f"{mode}: score columns present = {present or 'none'}")
        show_hits(hits, keys)

    detail("If hybrid returns _relevance_score from RRF, its range is roughly 0..~0.03 for "
           "k=60 and is RANK-based: it does not compare to a cosine similarity, and it "
           "shifts when top_k changes. A threshold tuned on cosine will silently reject "
           "everything or nothing.")


def probe_reranker_vocabulary() -> None:
    question("4b", "Is LanceDB's 'reranker' the model-free fusion the plan wants, or the "
                   "model the plan rejects?")
    try:
        from lancedb.rerankers import LinearCombinationReranker, RRFReranker
    except Exception as error:
        verdict("INFO", f"could not import lancedb.rerankers: {type(error).__name__}: {error}")
        return

    verdict("INFO", "LanceDB calls hybrid fusion a 'reranker'. RRFReranker and "
                    "LinearCombinationReranker are pure arithmetic — no model, no vendor, "
                    "no credential.")
    detail(f"RRFReranker default k = {getattr(RRFReranker(), 'K', 'n/a')}")
    detail(f"LinearCombinationReranker default weight = "
           f"{getattr(LinearCombinationReranker(), 'weight', 'n/a')}")
    detail("So decision 7 ('hybrid search, no reranker') is a vocabulary clash, not a "
           "contradiction — the plan must name WHICH fusion reranker it uses.")


# --------------------------------------------------------------------------------------
# Layer B — the llama-index wrapper the plan actually builds on
# --------------------------------------------------------------------------------------

def probe_llama_index(db_uri: str) -> None:
    question("5", "llama-index LanceDBVectorStore: does MetadataFilters push down in "
                  "HYBRID mode? (the layer the plan is built on)")

    try:
        from llama_index.core.schema import TextNode
        from llama_index.core.vector_stores.types import (
            FilterOperator,
            MetadataFilter,
            MetadataFilters,
            VectorStoreQuery,
            VectorStoreQueryMode,
        )
        from llama_index.vector_stores.lancedb import LanceDBVectorStore
    except Exception as error:
        verdict("ERROR", f"import failed: {type(error).__name__}: {error}")
        return

    def build_store(**extra):
        return LanceDBVectorStore(uri=db_uri, table_name="li_probe", mode="overwrite", **extra)

    try:
        store = build_store(query_type="hybrid")
    except Exception as error:
        verdict("INFO", f"hybrid store construction raised {type(error).__name__}: {error} "
                        f"— retrying with an explicit reranker")
        from lancedb.rerankers import RRFReranker
        store = build_store(query_type="hybrid", reranker=RRFReranker())

    nodes = [
        TextNode(
            id_=chunk.chunk_id,
            text=chunk.content,
            embedding=EMBEDDING.embed(chunk.content),
            metadata={
                "knowledge_base_id": chunk.knowledge_base_id,
                "document_id": chunk.document_id,
                "filename": chunk.filename,
                "access_scope": chunk.access_scope,
            },
        )
        for chunk in build_corpus()
    ]
    store.add(nodes)

    table = getattr(store, "_table", None)
    if table is not None:
        print(f"\n  {BOLD}how the wrapper stored our metadata (decides Q2's real answer){RESET}")
        for field in table.schema:
            detail(f"{field.name}: {field.type}")
        try:
            create_fts_index(table)
            detail("created an FTS index on the wrapper's text column")
        except Exception as error:
            verdict("INFO", f"could not create FTS index on the wrapper table: "
                            f"{type(error).__name__}: {error}")

    filters = MetadataFilters(filters=[
        MetadataFilter(key="knowledge_base_id", value="kb_a", operator=FilterOperator.EQ),
    ])

    for label, mode in (
        ("DEFAULT (vector)", VectorStoreQueryMode.DEFAULT),
        ("HYBRID", VectorStoreQueryMode.HYBRID),
    ):
        print(f"\n  {BOLD}mode = {label}{RESET}")
        query = VectorStoreQuery(
            query_embedding=EMBEDDING.embed(CANARY_TERM),
            query_str=CANARY_TERM,
            similarity_top_k=6,
            mode=mode,
            filters=filters,
        )
        try:
            result = store.query(query)
        except Exception as error:
            verdict("ERROR", f"{type(error).__name__}: {error}")
            detail(traceback.format_exc().strip().splitlines()[-1])
            continue

        returned = [
            (node.metadata.get("knowledge_base_id"), node.metadata.get("document_id"), node.node_id)
            for node in (result.nodes or [])
        ]
        for kb_id, doc_id, node_id in returned:
            detail(f"{kb_id}/{doc_id} {node_id}")
        detail(f"similarities: {result.similarities}")

        leaked = [row for row in returned if row[0] != "kb_a"]
        if leaked:
            verdict("FAIL", f"{len(leaked)} node(s) from another knowledge base leaked in "
                            f"{label} mode")
            detail("if raw lancedb passed Q1a and this fails, the wrapper is dropping the "
                   "predicate: reach through to the table, do not drop hybrid search")
        elif not returned:
            verdict("INFO", f"{label}: no nodes returned — filter may be over-restricting; "
                            f"check the metadata column path against the schema above")
        else:
            verdict("PASS", f"MetadataFilters pushed down in {label} mode")

    probe_wrapper_similarities(store, VectorStoreQuery, VectorStoreQueryMode)


def probe_wrapper_similarities(store, VectorStoreQuery, VectorStoreQueryMode) -> None:
    """Does the wrapper hand back a real score, or a min-max normalisation of the batch?

    If the first result is always 1.0 and the last always 0.0, then `similarities` is
    relative to whatever came back — and a threshold applied to it cannot mean
    "relevant enough", only "in the top slice". That would make the plan's
    RagChatProfile.score_threshold unimplementable at this layer.
    """
    question("5b", "llama-index: is `similarities` an absolute score or a batch "
                   "normalisation? (decides whether score_threshold can live here)")

    for top_k in (2, 3, 4, 6):
        query = VectorStoreQuery(
            query_embedding=EMBEDDING.embed("ingestion worker object store"),
            query_str="ingestion worker object store",
            similarity_top_k=top_k,
            mode=VectorStoreQueryMode.HYBRID,
        )
        try:
            result = store.query(query)
        except Exception as error:
            verdict("ERROR", f"top_k={top_k}: {type(error).__name__}: {error}")
            continue
        similarities = result.similarities or []
        detail(f"top_k={top_k}: {[round(value, 4) for value in similarities]}")

        if len(similarities) >= 2 and similarities[0] == 1.0 and similarities[-1] == 0.0:
            verdict("FAIL", f"top_k={top_k}: first=1.0 last=0.0 — batch-normalised, not absolute")
        elif similarities:
            verdict("PASS", f"top_k={top_k}: scores look absolute "
                            f"(range {min(similarities):.4f}..{max(similarities):.4f})")

    detail("Same query, same corpus, different top_k: if the numbers MOVE, the score is "
           "relative to the batch. A threshold on it silently changes meaning with top_k.")


# --------------------------------------------------------------------------------------

def main() -> None:
    import lancedb

    print(f"{BOLD}PROTOTYPE — LanceDB hybrid-search spike{RESET}")
    print(f"{DIM}throwaway; findings go into rag_embedded_stack_implementation_plan.md{RESET}")

    print(f"\n{BOLD}Installed versions (the plan says re-verify every pin){RESET}")
    for module_name in ("lancedb", "pyarrow", "pandas", "llama_index.core",
                        "llama_index.vector_stores.lancedb", "tantivy"):
        try:
            module = __import__(module_name, fromlist=["__version__"])
            detail(f"{module_name} == {getattr(module, '__version__', 'unknown')}")
        except Exception as error:
            detail(f"{module_name} -- not importable ({type(error).__name__})")

    if DB_DIR.exists():
        shutil.rmtree(DB_DIR)
    db = lancedb.connect(str(DB_DIR))

    table = db.create_table("chunks", schema=arrow_schema(), mode="overwrite")
    table.add([to_row(chunk) for chunk in build_corpus()])
    flavour = create_fts_index(table)
    detail(f"main probe table: {table.count_rows()} rows, FTS index {flavour}")

    probe_raw_isolation(table)
    probe_raw_document_filter(table)
    probe_delete_predicate(db)
    probe_fts_incrementality(db)
    probe_score_semantics(table)
    probe_reranker_vocabulary()
    probe_llama_index(str(DB_DIR))

    print(f"\n{BOLD}{'=' * 86}{RESET}")
    print(f"{BOLD}Done.{RESET} Q1a/Q5 FAIL => hybrid isolation is unsafe, plan §Hybrid retrieval "
          f"changes.\n       Q1a PASS + Q5 FAIL => reach through the wrapper.")
    print(f"{DIM}scratch data in {DB_DIR} — delete freely{RESET}")


if __name__ == "__main__":
    main()
