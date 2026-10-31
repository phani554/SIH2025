"""Hybrid retrieval: keyword (BM25) + vector (cosine), merged with Reciprocal Rank Fusion.

Why hybrid: invoice numbers, regulation ids and vendor names need exact keyword
matches; embeddings catch paraphrases ("fare revenue" ~ "ticket collections").
Why RRF: BM25 scores and cosine scores have different scales; RRF only uses
ranks, so no score normalisation or tuning is needed.

At this scale (thousands of chunks) a numpy scan is fast enough. In production
the vector side becomes a pgvector HNSW index query.
"""
import re
from collections import Counter

import numpy as np

CANDIDATES = 20   # how many each retriever returns before fusion


def keyword_search(conn, question: str, doc_ids: set[int] | None, limit: int = CANDIDATES) -> list[int]:
    # Turn the question into an FTS5 OR-query of its words (quoted, so symbols are safe).
    terms = [t for t in re.findall(r"\w+", question.lower()) if len(t) > 2]
    if not terms:
        return []
    fts_query = " OR ".join(f'"{t}"' for t in terms)
    rows = conn.execute(
        """SELECT c.chunk_id, c.doc_id FROM chunks_fts
           JOIN chunks c ON c.chunk_id = chunks_fts.rowid
           WHERE chunks_fts MATCH ? ORDER BY bm25(chunks_fts) LIMIT ?""",
        (fts_query, limit * 3),
    ).fetchall()
    return [r["chunk_id"] for r in rows if doc_ids is None or r["doc_id"] in doc_ids][:limit]


def vector_search(conn, query_vec: np.ndarray, doc_ids: set[int] | None, limit: int = CANDIDATES) -> list[int]:
    rows = conn.execute("SELECT chunk_id, doc_id, embedding FROM chunks WHERE embedding IS NOT NULL").fetchall()
    rows = [r for r in rows if doc_ids is None or r["doc_id"] in doc_ids]
    if not rows:
        return []
    matrix = np.vstack([np.frombuffer(r["embedding"], dtype=np.float32) for r in rows])
    scores = matrix @ query_vec            # vectors are normalised, so dot product = cosine
    best = np.argsort(-scores)[:limit]
    return [rows[i]["chunk_id"] for i in best]


def reciprocal_rank_fusion(rankings: list[list[int]], k: int = 60) -> list[int]:
    """score(chunk) = sum over lists of 1 / (k + rank). k=60 is the standard constant."""
    score: Counter = Counter()
    for ranking in rankings:
        for rank, chunk_id in enumerate(ranking, start=1):
            score[chunk_id] += 1.0 / (k + rank)
    return [chunk_id for chunk_id, _ in score.most_common()]


def docs_in_department(conn, department: str) -> set[int]:
    rows = conn.execute(
        """SELECT dd.doc_id FROM document_departments dd
           JOIN departments d ON d.dept_id = dd.dept_id WHERE d.name = ?""",
        (department,),
    ).fetchall()
    return {r["doc_id"] for r in rows}


def hybrid_search(conn, llm, question: str, department: str | None = None, top_k: int = 5) -> list[dict]:
    # Filter BEFORE retrieval, so a Finance query never sees Safety chunks.
    doc_ids = docs_in_department(conn, department) if department else None
    query_vec = llm.embed([question], task="query")[0]
    fused = reciprocal_rank_fusion([
        keyword_search(conn, question, doc_ids),
        vector_search(conn, query_vec, doc_ids),
    ])[:top_k]
    if not fused:
        return []
    placeholders = ",".join("?" * len(fused))
    rows = conn.execute(
        f"""SELECT c.chunk_id, c.doc_id, c.page, c.text, d.file_name
            FROM chunks c JOIN documents d ON d.doc_id = c.doc_id
            WHERE c.chunk_id IN ({placeholders})""",
        fused,
    ).fetchall()
    by_id = {r["chunk_id"]: dict(r) for r in rows}
    return [by_id[i] for i in fused if i in by_id]
