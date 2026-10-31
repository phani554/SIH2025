"""The ingestion pipeline. Every source (upload, Gmail) goes through ingest_file().

    bytes -> SHA-256 dedupe -> save file -> extract pages -> redact PII
          -> prompt-injection scan -> chunk (strategy from .env)
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
from ..security import looks_like_injection, redact_pii
from .analysis import analyze_document
from .chunking import chunk_pages
from .extraction import Page, extract_pages
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


def ingest_file(conn, llm, file_name: str, data: bytes, source: str = "upload",
                strategy: str | None = None, upload_dir: str | None = None) -> IngestResult:
    file_name = safe_file_name(file_name)
    digest = sha256_bytes(data)

    # 1. Dedupe: the same PDF forwarded five times is processed once.
    existing = conn.execute("SELECT doc_id, status FROM documents WHERE sha256 = ?",
                            (digest,)).fetchone()
    if existing:
        return IngestResult(existing["doc_id"], duplicate=True, status=existing["status"])

    # 2. Keep the original file: every answer can be traced back to it.
    folder = upload_dir or settings.upload_dir
    os.makedirs(folder, exist_ok=True)
    saved_path = os.path.join(folder, f"{digest[:12]}_{file_name}")
    with open(saved_path, "wb") as f:
        f.write(data)

    cur = conn.execute(
        "INSERT INTO documents(sha256, file_name, source, saved_path) VALUES (?, ?, ?, ?)",
        (digest, file_name, source, saved_path),
    )
    doc_id = cur.lastrowid
    audit(conn, "INGEST", f"{source}: {file_name}", doc_id)

    # 3. Extract, then redact PII so it never reaches the LLM or the search index.
    pages = extract_pages(file_name, data)
    if settings.redact_pii:
        pages, found = _redact_pages(pages)
        if found:
            audit(conn, "REDACT", json.dumps(found), doc_id)
    full_text = "\n".join(p.text for p in pages)
    if not full_text.strip():
        _set_status(conn, doc_id, "NEEDS_REVIEW")
        audit(conn, "ANALYZE", "no text extracted (scanned?)", doc_id)
        return IngestResult(doc_id, duplicate=False, status="NEEDS_REVIEW")

    # 4. Chunk + embed + index. Chunks that try to instruct the LLM are flagged.
    chunks = chunk_pages(pages, settings.chunk_size_words, settings.chunk_overlap_words,
                         strategy or settings.chunk_strategy)
    vectors = llm.embed([c.text for c in chunks], task="document")
    flags = [looks_like_injection(c.text) for c in chunks]
    conn.executemany(
        "INSERT INTO chunks(doc_id, chunk_no, page, text, embedding, flagged) VALUES (?, ?, ?, ?, ?, ?)",
        [(doc_id, c.chunk_no, c.page, c.text, v.astype(np.float32).tobytes(), int(f))
         for c, v, f in zip(chunks, vectors, flags)],
    )
    if any(flags):
        audit(conn, "INJECTION_FLAG", f"{sum(flags)} chunk(s) flagged", doc_id)

    # 5. Understand: one validated LLM call (flagged chunks left out).
    safe_text = "\n".join(c.text for c, f in zip(chunks, flags) if not f) if any(flags) else full_text
    try:
        analysis = analyze_document(llm, file_name, safe_text)
    except LLMError as exc:
        _set_status(conn, doc_id, "NEEDS_REVIEW")
        audit(conn, "ANALYZE", f"failed: {exc}", doc_id)
        return IngestResult(doc_id, duplicate=False, status="NEEDS_REVIEW")

    save_analysis(conn, doc_id, analysis, force_review=any(flags))
    return IngestResult(doc_id, duplicate=False,
                        status="NEEDS_REVIEW" if any(flags) else _status_for(analysis))


def _redact_pages(pages: list[Page]) -> tuple[list[Page], dict[str, int]]:
    clean, totals = [], {}
    for page in pages:
        text, counts = redact_pii(page.text)
        clean.append(Page(page.number, text))
        for label, n in counts.items():
            totals[label] = totals.get(label, 0) + n
    return clean, totals


def _status_for(analysis) -> str:
    # Human-in-the-loop: low confidence or critical items wait for a reviewer.
    if analysis.confidence < settings.review_threshold or analysis.urgency == "Critical":
        return "NEEDS_REVIEW"
    return "ANALYZED"


def _set_status(conn, doc_id: int, status: str) -> None:
    conn.execute("UPDATE documents SET status = ? WHERE doc_id = ?", (status, doc_id))


def save_analysis(conn, doc_id: int, analysis, force_review: bool = False) -> None:
    status = "NEEDS_REVIEW" if force_review else _status_for(analysis)
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
