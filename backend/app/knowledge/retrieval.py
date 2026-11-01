"""Retrieval over the knowledge store: BM25 keyword search, vector search, RRF fusion.

Why hybrid: invoice numbers, circular ids and vendor names need exact keyword
matches; embeddings catch paraphrases ("fare revenue" ~ "ticket collections").
Why RRF: BM25 and cosine scores have different scales; RRF only uses ranks,
so no score normalisation or tuning is needed.

This layer never calls the LLM: the orchestrator passes in the query vector.
At this scale a numpy scan is fast enough; in production the vector side becomes
a pgvector HNSW index query.
"""
import re
from collections import Counter

import numpy as np

CANDIDATES = 20   # how many each retriever returns before fusion
RRF_K = 60

FTS_SQL = """SELECT c.chunk_id, c.doc_id, bm25(chunks_fts) AS score FROM chunks_fts
JOIN chunks c ON c.chunk_id = chunks_fts.rowid
WHERE chunks_fts MATCH ? ORDER BY score LIMIT ?"""


def docs_in_department(conn, department: str) -> set[int]:
    """Documents this department owns (its PRIMARY department). Access follows the document's
    one routed department, so a secondary guess by Level 1 never widens who can read it.
    Documents pending review or rejected have no department, so no viewer can retrieve them."""
    rows = conn.execute(
        """SELECT dd.doc_id FROM document_departments dd
           JOIN departments d ON d.dept_id = dd.dept_id
           WHERE d.name = ? AND dd.is_primary = 1""", (department,)).fetchall()
    return {r["doc_id"] for r in rows}


def searchable_docs(conn, department: str | None) -> set[int]:
    """What a question may search: one department's documents, or (no department) every
    document except REJECTED ones. A rejected document stays stored for the audit trail
    but never feeds an answer."""
    if department:
        return docs_in_department(conn, department)
    return {r["doc_id"] for r in conn.execute("SELECT doc_id FROM documents WHERE status != 'REJECTED'")}


def fts_query(question: str) -> str:
    # Each word quoted and OR-ed, so symbols in the question can't break FTS5 syntax.
    terms = [t for t in re.findall(r"\w+", question.lower()) if len(t) > 2]
    return " OR ".join(f'"{t}"' for t in terms)


def keyword_search(conn, question: str, doc_ids: set[int] | None, limit: int = CANDIDATES):
    """Returns (match_string, [(chunk_id, bm25)]). In SQLite's bm25(), lower = better."""
    query = fts_query(question)
    if not query:
        return query, []
    rows = conn.execute(FTS_SQL, (query, limit * 3)).fetchall()
    hits = [(r["chunk_id"], round(r["score"], 3)) for r in rows if doc_ids is None or r["doc_id"] in doc_ids]
    return query, hits[:limit]


def vector_search(conn, query_vec: np.ndarray, doc_ids: set[int] | None, limit: int = CANDIDATES):
    """Returns [(chunk_id, cosine)]. Vectors are unit length, so dot product = cosine."""
    rows = conn.execute("SELECT chunk_id, doc_id, embedding FROM chunks WHERE embedding IS NOT NULL").fetchall()
    rows = [r for r in rows if (doc_ids is None or r["doc_id"] in doc_ids)
            and len(r["embedding"]) == query_vec.size * 4]      # skip vectors from another provider
    if not rows:
        return []
    matrix = np.vstack([np.frombuffer(r["embedding"], dtype=np.float32) for r in rows])
    scores = matrix @ query_vec
    best = np.argsort(-scores)[:limit]
    return [(rows[i]["chunk_id"], round(float(scores[i]), 4)) for i in best]


def reciprocal_rank_fusion(rankings: list[list[int]], k: int = RRF_K) -> list[tuple[int, float]]:
    """score(chunk) = sum over lists of 1 / (k + rank). k=60 is the standard constant."""
    score: Counter = Counter()
    for ranking in rankings:
        for rank, chunk_id in enumerate(ranking, start=1):
            score[chunk_id] += 1.0 / (k + rank)
    return [(cid, round(s, 5)) for cid, s in score.most_common()]


def load_chunks(conn, chunk_ids: list[int]) -> list[dict]:
    if not chunk_ids:
        return []
    placeholders = ",".join("?" * len(chunk_ids))
    rows = conn.execute(
        f"""SELECT c.chunk_id, c.doc_id, c.chunk_no, c.page, c.text, d.file_name
            FROM chunks c JOIN documents d ON d.doc_id = c.doc_id
            WHERE c.chunk_id IN ({placeholders})""", chunk_ids).fetchall()
    by_id = {r["chunk_id"]: dict(r) for r in rows}
    return [by_id[i] for i in chunk_ids if i in by_id]


def describe(conn, chunk_id: int, cache: dict) -> dict:
    """File name and chunk number for a chunk id (for the trace tables)."""
    if chunk_id not in cache:
        r = conn.execute("""SELECT d.file_name, c.chunk_no FROM chunks c JOIN documents d
                            ON d.doc_id = c.doc_id WHERE c.chunk_id = ?""", (chunk_id,)).fetchone()
        cache[chunk_id] = {"file": r["file_name"], "chunk_no": r["chunk_no"]}
    return cache[chunk_id]
