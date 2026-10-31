"""Retrieval: keyword (BM25), vector (cosine), hybrid (RRF), optionally with HyDE.

Why hybrid: invoice numbers, regulation ids and vendor names need exact keyword
matches; embeddings catch paraphrases ("fare revenue" ~ "ticket collections").
Why RRF: BM25 scores and cosine scores have different scales; RRF only uses
ranks, so no score normalisation or tuning is needed.

HyDE (Hypothetical Document Embeddings): a short question and a long document
paragraph embed differently. So we ask the LLM to write a fake answer paragraph
and embed THAT for the vector search. The fake text is never shown to the user;
it only steers the search. Keyword search still uses the real question.

At this scale (thousands of chunks) a numpy scan is fast enough. In production
the vector side becomes a pgvector HNSW index query.
"""
import re
from collections import Counter

import numpy as np

CANDIDATES = 20   # how many each retriever returns before fusion
MODES = ("keyword", "vector", "hybrid")

HYDE_PROMPT = """HYPOTHETICAL DOCUMENT
Write a short passage (3-4 sentences) that could appear in a Kochi Metro (KMRL)
document and would answer the question below. Invent plausible details; it is
only used to improve search and is never shown to anyone.
QUESTION: {question}
PASSAGE:"""


def keyword_search(conn, question: str, doc_ids: set[int] | None, limit: int = CANDIDATES) -> list[int]:
    # Turn the question into an FTS5 OR-query of its words (quoted, so symbols are safe).
    terms = [t for t in re.findall(r"\w+", question.lower()) if len(t) > 2]
    if not terms:
        return []
    fts_query = " OR ".join(f'"{t}"' for t in terms)
    rows = conn.execute(
        """SELECT c.chunk_id, c.doc_id FROM chunks_fts
           JOIN chunks c ON c.chunk_id = chunks_fts.rowid
           WHERE chunks_fts MATCH ? AND c.flagged = 0
           ORDER BY bm25(chunks_fts) LIMIT ?""",
        (fts_query, limit * 3),
    ).fetchall()
    return [r["chunk_id"] for r in rows if doc_ids is None or r["doc_id"] in doc_ids][:limit]


def vector_search(conn, query_vec: np.ndarray, doc_ids: set[int] | None, limit: int = CANDIDATES) -> list[int]:
    rows = conn.execute(
        "SELECT chunk_id, doc_id, embedding FROM chunks WHERE embedding IS NOT NULL AND flagged = 0"
    ).fetchall()
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


def query_vector(llm, question: str, use_hyde: bool) -> np.ndarray:
    if use_hyde:
        hypothetical = llm.generate_text(HYDE_PROMPT.format(question=question))
        # Embed question + fake passage together, so a bad fake can't drift too far.
        return llm.embed([f"{question}\n{hypothetical}"], task="document")[0]
    return llm.embed([question], task="query")[0]


def search(conn, llm, question: str, department: str | None = None, top_k: int = 5,
           mode: str = "hybrid", use_hyde: bool = False) -> list[dict]:
    if mode not in MODES:
        raise ValueError(f"mode must be one of {MODES}")
    # Filter BEFORE retrieval, so a Finance user never even ranks Safety chunks.
    doc_ids = docs_in_department(conn, department) if department else None

    rankings = []
    if mode in ("keyword", "hybrid"):
        rankings.append(keyword_search(conn, question, doc_ids))
    if mode in ("vector", "hybrid"):
        rankings.append(vector_search(conn, query_vector(llm, question, use_hyde), doc_ids))
    ranked = reciprocal_rank_fusion(rankings)[:top_k]
    return load_chunks(conn, ranked)


def load_chunks(conn, chunk_ids: list[int]) -> list[dict]:
    if not chunk_ids:
        return []
    placeholders = ",".join("?" * len(chunk_ids))
    rows = conn.execute(
        f"""SELECT c.chunk_id, c.doc_id, c.page, c.text, d.file_name
            FROM chunks c JOIN documents d ON d.doc_id = c.doc_id
            WHERE c.chunk_id IN ({placeholders})""",
        chunk_ids,
    ).fetchall()
    by_id = {r["chunk_id"]: dict(r) for r in rows}
    return [by_id[i] for i in chunk_ids if i in by_id]
