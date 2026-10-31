"""The ingestion pipeline. Every source (upload, Gmail) goes through ingest_file().

    bytes -> SHA-256 dedupe -> save file -> extract pages -> chunk
          -> embed chunks -> store chunks (+ FTS index via trigger)
          -> LLM analysis -> validated JSON -> departments, action items
          -> status ANALYZED or NEEDS_REVIEW -> audit log
"""
import hashlib
import json
import os
from dataclasses import dataclass

import numpy as np

from ..config import settings
from ..db import audit
from .analysis import analyze_document
from .chunking import chunk_pages
from .extraction import extract_pages
from .llm import LLMError


@dataclass
class IngestResult:
    doc_id: int
    duplicate: bool
    status: str


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def safe_file_name(name: str) -> str:
    return os.path.basename(name).replace("..", "_") or "file"


def ingest_file(conn, llm, file_name: str, data: bytes, source: str = "upload") -> IngestResult:
    file_name = safe_file_name(file_name)
    digest = sha256_bytes(data)

    # 1. Dedupe: the same PDF forwarded five times is processed once.
    existing = conn.execute("SELECT doc_id, status FROM documents WHERE sha256 = ?",
                            (digest,)).fetchone()
    if existing:
        return IngestResult(existing["doc_id"], duplicate=True, status=existing["status"])

    # 2. Keep the original file: every answer can be traced back to it.
    os.makedirs(settings.upload_dir, exist_ok=True)
    saved_path = os.path.join(settings.upload_dir, f"{digest[:12]}_{file_name}")
    with open(saved_path, "wb") as f:
        f.write(data)

    cur = conn.execute(
        "INSERT INTO documents(sha256, file_name, source, saved_path) VALUES (?, ?, ?, ?)",
        (digest, file_name, source, saved_path),
    )
    doc_id = cur.lastrowid
    audit(conn, "INGEST", f"{source}: {file_name}", doc_id)

    # 3. Extract + chunk + embed + index.
    pages = extract_pages(file_name, data)
    full_text = "\n".join(p.text for p in pages)
    if not full_text.strip():
        _set_status(conn, doc_id, "NEEDS_REVIEW")
        audit(conn, "ANALYZE", "no text extracted (scanned?)", doc_id)
        return IngestResult(doc_id, duplicate=False, status="NEEDS_REVIEW")

    chunks = chunk_pages(pages, settings.chunk_size_words, settings.chunk_overlap_words)
    vectors = llm.embed([c.text for c in chunks], task="document")
    conn.executemany(
        "INSERT INTO chunks(doc_id, chunk_no, page, text, embedding) VALUES (?, ?, ?, ?, ?)",
        [(doc_id, c.chunk_no, c.page, c.text, v.astype(np.float32).tobytes())
         for c, v in zip(chunks, vectors)],
    )

    # 4. Understand: one validated LLM call.
    try:
        analysis = analyze_document(llm, file_name, full_text)
    except LLMError as exc:
        _set_status(conn, doc_id, "NEEDS_REVIEW")
        audit(conn, "ANALYZE", f"failed: {exc}", doc_id)
        return IngestResult(doc_id, duplicate=False, status="NEEDS_REVIEW")

    save_analysis(conn, doc_id, analysis)
    return IngestResult(doc_id, duplicate=False, status=_status_for(analysis))


def _status_for(analysis) -> str:
    # Human-in-the-loop: low confidence or critical items wait for a reviewer.
    if analysis.confidence < settings.review_threshold or analysis.urgency == "Critical":
        return "NEEDS_REVIEW"
    return "ANALYZED"


def _set_status(conn, doc_id: int, status: str) -> None:
    conn.execute("UPDATE documents SET status = ? WHERE doc_id = ?", (status, doc_id))


def save_analysis(conn, doc_id: int, analysis) -> None:
    status = _status_for(analysis)
    conn.execute(
        """UPDATE documents SET doc_type = ?, summary = ?, urgency = ?, confidence = ?,
               status = ?, analysis_json = ? WHERE doc_id = ?""",
        (analysis.doc_type, analysis.summary, analysis.urgency, analysis.confidence,
         status, analysis.model_dump_json(), doc_id),
    )
    set_departments(conn, doc_id, analysis.department, analysis.secondary_departments,
                    analysis.confidence)
    conn.executemany(
        "INSERT INTO action_items(doc_id, action, owner, priority, due) VALUES (?, ?, ?, ?, ?)",
        [(doc_id, a.action, a.owner, a.priority, a.due) for a in analysis.action_items],
    )
    audit(conn, "ANALYZE", json.dumps({"department": analysis.department,
                                       "confidence": analysis.confidence,
                                       "status": status}), doc_id)


def set_departments(conn, doc_id: int, primary: str, secondary: list[str],
                    confidence: float | None) -> None:
    conn.execute("DELETE FROM document_departments WHERE doc_id = ?", (doc_id,))
    for name in [primary] + [d for d in secondary if d != primary]:
        conn.execute(
            """INSERT INTO document_departments(doc_id, dept_id, is_primary, confidence)
               SELECT ?, dept_id, ?, ? FROM departments WHERE name = ?""",
            (doc_id, int(name == primary), confidence if name == primary else None, name),
        )
