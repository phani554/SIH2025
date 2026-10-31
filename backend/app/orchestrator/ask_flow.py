"""Question workflow. The orchestrator calls one layer per step and traces each one.

    api        auth, query_received                       (done by the /ask route)
    orch       plan_run
    knowledge  department_filter -> keyword_search_bm25
    llm        hyde_generation -> embed_query
    knowledge  vector_search_cosine -> rrf_fusion
    llm        llm_answer -> citation_check
    actions    audit_query
"""
import json

from ..actions.audit import audit
from ..knowledge import retrieval
from ..llm.grounding import NOT_FOUND, SUPPORT_THRESHOLD, build_context, check_citations
from ..llm.prompts import ANSWER_PROMPT, HYDE_PROMPT
from .tracing import Tracer

MODES = ("keyword", "vector", "hybrid")


def answer_question(conn, llm, question: str, department: str | None = None, top_k: int = 5,
                    use_hyde: bool = False, mode: str = "hybrid", tracer: Tracer | None = None) -> dict:
    """Returns {"answer", "citations", "grounded", "faithfulness", "run_id"}."""
    tracer = tracer or Tracer("adhoc")          # unsaved tracer for evals
    with tracer.step("plan_run", "orchestrator") as s:
        llm_calls = 1 + (1 if use_hyde and mode != "keyword" else 0)
        tracer.plan = {"plan": {"steps": _planned_steps(mode, use_hyde), "max_llm_calls": llm_calls,
                                "max_retries": 0, "top_k": top_k, "mode": mode, "hyde": use_hyde}}
        s.output = f"mode={mode}, HyDE={'on' if use_hyde else 'off'}, top_k={top_k}, max {llm_calls} LLM call(s)"
        s.detail = tracer.plan["plan"]

    chunks = search(conn, llm, question, department, top_k, mode, use_hyde, tracer)
    if not chunks:
        tracer.skip("llm_answer", "llm", "no chunks retrieved: nothing to ground an answer on")
        return _done(conn, tracer, question, NOT_FOUND, [], False, 0.0)

    with tracer.step("llm_answer", "llm") as s:
        prompt = ANSWER_PROMPT.format(not_found=NOT_FOUND, context=build_context(chunks), question=question)
        reply = llm.generate(prompt)
        s.input = f"{len(chunks)} numbered chunk(s), {len(prompt):,} chars"
        s.output = reply.text[:200]
        s.detail = {"provider": llm.name, "model": reply.model, "prompt": prompt, "raw_response": reply.text,
                    "tokens": {"prompt": reply.prompt_tokens, "completion": reply.completion_tokens}}
    answer = reply.text.strip()

    with tracer.step("citation_check", "llm") as s:
        faithfulness, supported, table = check_citations(answer, chunks)
        grounded = NOT_FOUND not in answer and any(supported.values())
        s.input = f"a sentence is supported if >= {SUPPORT_THRESHOLD:.0%} of its words are in the cited chunk"
        s.output = f"faithfulness {faithfulness:.2f}; " + ("grounded" if grounded else "NOT grounded -> refuse")
        s.detail = {"sentences": table, "faithfulness": round(faithfulness, 2), "grounded": grounded}

    citations = [{"n": n, "chunk_id": chunks[n - 1]["chunk_id"], "doc_id": chunks[n - 1]["doc_id"],
                  "file_name": chunks[n - 1]["file_name"], "page": chunks[n - 1]["page"],
                  "snippet": chunks[n - 1]["text"][:300], "supported": ok}
                 for n, ok in sorted(supported.items())]
    if not grounded:
        return _done(conn, tracer, question, NOT_FOUND, [], False, 0.0)
    return _done(conn, tracer, question, answer, citations, True, round(faithfulness, 2))


def search(conn, llm, question: str, department: str | None, top_k: int, mode: str,
           use_hyde: bool, tracer: Tracer) -> list[dict]:
    if mode not in MODES:
        raise ValueError(f"mode must be one of {MODES}")
    names: dict = {}

    # Filter BEFORE ranking, so other departments' chunks are never even scored.
    with tracer.step("department_filter", "knowledge") as s:
        doc_ids = retrieval.docs_in_department(conn, department) if department else None
        s.input = f"department = {department or 'all'}"
        s.output = f"{len(doc_ids)} document(s) searchable" if doc_ids is not None else "no filter: all documents"
        s.detail = {"department": department, "doc_ids": sorted(doc_ids) if doc_ids is not None else "all"}

    rankings = []
    if mode in ("keyword", "hybrid"):
        with tracer.step("keyword_search_bm25", "knowledge") as s:
            match, hits = retrieval.keyword_search(conn, question, doc_ids)
            rankings.append([cid for cid, _ in hits])
            s.input = f"FTS5 MATCH {match}"
            s.output = f"{len(hits)} hit(s)"
            s.detail = {"sql": retrieval.FTS_SQL, "match": match,
                        "top": [{"rank": i, "chunk_id": cid, "bm25": sc, **retrieval.describe(conn, cid, names)}
                                for i, (cid, sc) in enumerate(hits[:top_k], 1)]}

    if mode in ("vector", "hybrid"):
        query_text = question
        if use_hyde:
            with tracer.step("hyde_generation", "llm") as s:
                prompt = HYDE_PROMPT.format(question=question)
                reply = llm.generate(prompt)
                query_text = f"{question}\n{reply.text}"    # question + fake passage, so it can't drift far
                s.output = reply.text[:200]
                s.detail = {"prompt": prompt, "raw_response": reply.text, "model": reply.model,
                            "tokens": {"prompt": reply.prompt_tokens, "completion": reply.completion_tokens},
                            "embedded_text": query_text}
        else:
            tracer.skip("hyde_generation", "llm", "HyDE off: embedding the question itself")
        with tracer.step("embed_query", "llm") as s:
            query_vec = llm.embed([query_text])[0]
            s.input = "question + HyDE passage" if use_hyde else "question"
            s.output = f"1 vector of {query_vec.size} dims ({llm.name})"
        with tracer.step("vector_search_cosine", "knowledge") as s:
            hits = retrieval.vector_search(conn, query_vec, doc_ids)
            rankings.append([cid for cid, _ in hits])
            s.output = f"{len(hits)} hit(s)"
            s.detail = {"top": [{"rank": i, "chunk_id": cid, "cosine": sc, **retrieval.describe(conn, cid, names)}
                                for i, (cid, sc) in enumerate(hits[:top_k], 1)]}

    with tracer.step("rrf_fusion", "knowledge") as s:
        fused = retrieval.reciprocal_rank_fusion(rankings)[:top_k]
        ranks = [{cid: i for i, cid in enumerate(r, 1)} for r in rankings]
        s.input = f"{len(rankings)} ranked list(s), k={retrieval.RRF_K}"
        s.output = f"top {len(fused)} chunk(s) kept"
        s.detail = {"formula": "score = sum of 1 / (60 + rank)",
                    "fused": [{"final_rank": i, "chunk_id": cid, "rrf_score": sc,
                               "ranks_in_each_list": [r.get(cid) for r in ranks], **retrieval.describe(conn, cid, names)}
                              for i, (cid, sc) in enumerate(fused, 1)]}
    return retrieval.load_chunks(conn, [cid for cid, _ in fused])


def _done(conn, tracer: Tracer, question: str, answer: str, citations: list, grounded: bool,
          faithfulness: float) -> dict:
    tracer.finish("ANSWERED" if grounded else "REFUSED", question[:200])
    run_id = None
    if tracer.kind == "ask":
        with tracer.step("audit_query", "actions") as s:
            s.output = "question, chunk ids and faithfulness written to the audit log"
        run_id = tracer.save(conn)
        audit(conn, "QUERY", json.dumps({"q": question, "run_id": run_id, "faithfulness": faithfulness}),
              actor=tracer.actor)
    return {"answer": answer, "citations": citations, "grounded": grounded,
            "faithfulness": faithfulness, "run_id": run_id}


def _planned_steps(mode: str, use_hyde: bool) -> list[str]:
    steps = ["auth", "query_received", "plan_run", "department_filter"]
    if mode in ("keyword", "hybrid"):
        steps.append("keyword_search_bm25")
    if mode in ("vector", "hybrid"):
        steps += (["hyde_generation"] if use_hyde else []) + ["embed_query", "vector_search_cosine"]
    return steps + ["rrf_fusion", "llm_answer", "citation_check", "audit_query"]
