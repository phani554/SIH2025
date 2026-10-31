"""Knowledge store: documents, chunks, vectors and the FTS5 index (SQLite).

Everything that writes documents/chunks lives here, so the other layers never
write SQL against these tables directly.
"""
import json
import os

import numpy as np

from ..config import settings

DEDUPE_SQL = "SELECT doc_id FROM documents WHERE sha256 = ?"


def find_by_sha256(conn, digest: str) -> int | None:
    row = conn.execute(DEDUPE_SQL, (digest,)).fetchone()
    return row["doc_id"] if row else None


def save_original(conn, digest: str, file_name: str, data: bytes, source: str,
                  upload_dir: str | None = None) -> int:
    """Keep the original bytes on disk and create the document row. Returns doc_id."""
    folder = upload_dir or settings.upload_dir
    os.makedirs(folder, exist_ok=True)
    path = os.path.join(folder, f"{digest[:12]}_{file_name}")
    with open(path, "wb") as f:
        f.write(data)
    return conn.execute("INSERT INTO documents(sha256, file_name, source, saved_path) VALUES (?, ?, ?, ?)",
                        (digest, file_name, source, path)).lastrowid


def add_chunks(conn, doc_id: int, chunks, vectors) -> None:
    """A vector may be None (embedding provider down): the chunk stays keyword-searchable.
    A trigger copies each chunk's text into the FTS5 index."""
    conn.executemany(
        "INSERT INTO chunks(doc_id, chunk_no, page, text, embedding) VALUES (?, ?, ?, ?, ?)",
        [(doc_id, c.chunk_no, c.page, c.text, None if v is None else v.astype(np.float32).tobytes())
         for c, v in zip(chunks, vectors)])


def save_analysis(conn, doc_id: int, level1, level2, status: str, reasons: list[str]) -> None:
    conn.execute(
        """UPDATE documents SET doc_type = ?, summary = ?, urgency = ?, confidence = ?, status = ?,
               review_reasons = ?, l1_json = ?, l2_json = ? WHERE doc_id = ?""",
        (level1.doc_type if level1 else None, level1.summary if level1 else None,
         level1.urgency if level1 else None, level1.primary.confidence if level1 else None,
         status, json.dumps(reasons), level1.model_dump_json() if level1 else None,
         level2.model_dump_json() if level2 else None, doc_id))
    if level1:
        set_departments(conn, doc_id, [(d.name, d.confidence) for d in level1.departments])


def set_departments(conn, doc_id: int, departments: list[tuple[str, float | None]]) -> None:
    """departments: [(name, confidence)], primary first."""
    conn.execute("DELETE FROM document_departments WHERE doc_id = ?", (doc_id,))
    for i, (name, confidence) in enumerate(departments):
        conn.execute(
            """INSERT OR IGNORE INTO document_departments(doc_id, dept_id, is_primary, confidence)
               SELECT ?, dept_id, ?, ? FROM departments WHERE name = ?""",
            (doc_id, int(i == 0), confidence, name))
