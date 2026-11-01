"""SQLite storage. The same tables port to Postgres + pgvector for production.

Tables
  documents             one row per unique file (sha256 is UNIQUE -> dedupe is a DB rule)
  chunks                text pieces of a document, with their embedding
  chunks_fts            SQLite FTS5 index over chunk text, used for keyword (BM25) search
  departments           the 8 KMRL departments
  document_departments  junction: a document can concern several departments
  action_items          tasks extracted from a document
  audit_log             who did what, when (FKs use SET NULL so history survives deletes)
  runs, run_steps       the trace behind "Show me how": every step of every upload and question
  api_keys              hashed API keys with a role and (for viewers) a department
  v_chunk_lineage       VIEW: every chunk with its source document, page, vector size and
                        the document-level analysis (open it in DB Browser for SQLite)
"""
import sqlite3
from contextlib import contextmanager

from .config import DEPARTMENTS, settings

SCHEMA = """
CREATE TABLE IF NOT EXISTS documents (
    doc_id       INTEGER PRIMARY KEY,
    sha256       TEXT NOT NULL UNIQUE,
    file_name    TEXT NOT NULL,
    source       TEXT NOT NULL,              -- upload:<who uploaded it>
    saved_path   TEXT,
    doc_type     TEXT,
    summary      TEXT,
    urgency      TEXT,
    confidence   REAL,
    status       TEXT NOT NULL DEFAULT 'NEW', -- NEW / ANALYZED / NEEDS_REVIEW / APPROVED / REJECTED
    language     TEXT,                       -- e.g. "English", "English + Malayalam"
    l1_json      TEXT,                       -- Level 1: departments, urgency, summary (validated)
    l2_json      TEXT,                       -- Level 2: dates, amounts, regulation ids, vendors, actions
    review_reasons TEXT,                     -- why the gate sent it to review (JSON list)
    routing_json TEXT,                       -- department routing: chunk signals vs Level 1 vs Decisions API
    created_at   TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_documents_status ON documents(status, created_at);

CREATE TABLE IF NOT EXISTS chunks (
    chunk_id   INTEGER PRIMARY KEY,
    doc_id     INTEGER NOT NULL REFERENCES documents(doc_id) ON DELETE CASCADE,
    chunk_no   INTEGER NOT NULL,
    page       INTEGER,
    text       TEXT NOT NULL,
    embedding  BLOB,                          -- float32 vector; pgvector column in production
    UNIQUE (doc_id, chunk_no)
);

CREATE VIRTUAL TABLE IF NOT EXISTS chunks_fts USING fts5(
    text, content='chunks', content_rowid='chunk_id'
);
CREATE TRIGGER IF NOT EXISTS chunks_ai AFTER INSERT ON chunks BEGIN
    INSERT INTO chunks_fts(rowid, text) VALUES (new.chunk_id, new.text);
END;
CREATE TRIGGER IF NOT EXISTS chunks_ad AFTER DELETE ON chunks BEGIN
    INSERT INTO chunks_fts(chunks_fts, rowid, text) VALUES ('delete', old.chunk_id, old.text);
END;

-- Read-only view for humans: chunk -> page -> document -> analysis, in one row.
CREATE VIEW IF NOT EXISTS v_chunk_lineage AS
SELECT c.chunk_id, c.chunk_no, c.page,
       d.doc_id, d.file_name, substr(d.sha256, 1, 12) AS sha256_12, d.status,
       (SELECT group_concat(dp.name, ', ') FROM document_departments dd
          JOIN departments dp ON dp.dept_id = dd.dept_id WHERE dd.doc_id = d.doc_id) AS departments,
       d.doc_type, d.urgency, round(d.confidence, 2) AS confidence,
       length(c.text) AS chars,
       CASE WHEN c.embedding IS NULL THEN 0 ELSE length(c.embedding) / 4 END AS vector_dims,
       instr(c.text, '[Figure ') > 0 AS has_figure_text,
       c.text,
       d.summary AS doc_summary,
       d.l2_json AS doc_entities
FROM chunks c JOIN documents d ON d.doc_id = c.doc_id;

CREATE TABLE IF NOT EXISTS departments (
    dept_id INTEGER PRIMARY KEY,
    name    TEXT NOT NULL UNIQUE
);

CREATE TABLE IF NOT EXISTS document_departments (
    doc_id     INTEGER REFERENCES documents(doc_id) ON DELETE CASCADE,
    dept_id    INTEGER REFERENCES departments(dept_id) ON DELETE RESTRICT,
    is_primary INTEGER NOT NULL DEFAULT 0,
    confidence REAL,
    PRIMARY KEY (doc_id, dept_id)
);

CREATE TABLE IF NOT EXISTS action_items (
    action_id   INTEGER PRIMARY KEY,
    doc_id      INTEGER NOT NULL REFERENCES documents(doc_id) ON DELETE CASCADE,
    action      TEXT NOT NULL,
    owner       TEXT,
    priority    TEXT,
    due         TEXT,
    confidence  REAL
);

CREATE TABLE IF NOT EXISTS audit_log (
    audit_id INTEGER PRIMARY KEY,
    doc_id   INTEGER REFERENCES documents(doc_id) ON DELETE SET NULL,
    actor    TEXT NOT NULL DEFAULT 'system',
    action   TEXT NOT NULL,                  -- INGEST / ANALYZE / QUERY / REVIEW / DELETE
    detail   TEXT,
    at       TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_audit_time ON audit_log(at);

-- Tracing: one run per upload or question, one row per step it performed.
CREATE TABLE IF NOT EXISTS runs (
    run_id      INTEGER PRIMARY KEY,
    kind        TEXT NOT NULL,               -- ingest / ask
    doc_id      INTEGER REFERENCES documents(doc_id) ON DELETE SET NULL,
    actor       TEXT,                        -- API key name
    role        TEXT,
    department  TEXT,
    status      TEXT NOT NULL,               -- ANALYZED / NEEDS_REVIEW / DUPLICATE / REJECTED / ANSWERED / REFUSED
    summary     TEXT,
    plan_json   TEXT,                        -- preliminary analysis + run plan
    started_at  TEXT NOT NULL,
    duration_ms REAL
);
CREATE INDEX IF NOT EXISTS idx_runs_doc ON runs(doc_id);

CREATE TABLE IF NOT EXISTS run_steps (
    step_id        INTEGER PRIMARY KEY,
    run_id         INTEGER NOT NULL REFERENCES runs(run_id) ON DELETE CASCADE,
    seq            INTEGER NOT NULL,
    name           TEXT NOT NULL,
    layer          TEXT NOT NULL,             -- api / orchestrator / ingestion / knowledge / llm / actions
    status         TEXT NOT NULL,             -- ok / retried / failed / skipped
    started_at     TEXT,
    duration_ms    REAL,
    input_summary  TEXT,
    output_summary TEXT,
    detail_json    TEXT                       -- drill-down: prompt, raw output, scores, SQL
);

CREATE TABLE IF NOT EXISTS api_keys (
    key_id     INTEGER PRIMARY KEY,
    key_hash   TEXT NOT NULL UNIQUE,          -- SHA-256 of the key; the key itself is never stored
    name       TEXT NOT NULL,
    role       TEXT NOT NULL CHECK (role IN ('admin', 'reviewer', 'viewer')),
    department TEXT,                          -- viewers are limited to this department
    active     INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

"""


def connect(path: str | None = None) -> sqlite3.Connection:
    conn = sqlite3.connect(path or settings.db_path, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


@contextmanager
def get_conn(path: str | None = None):
    """Open a connection, commit on success, roll back on error, always close."""
    conn = connect(path)
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_db(path: str | None = None) -> None:
    with get_conn(path) as conn:
        conn.executescript(SCHEMA)
        cols = {r[1] for r in conn.execute("PRAGMA table_info(documents)")}
        if "routing_json" not in cols:            # databases created before routing existed
            conn.execute("ALTER TABLE documents ADD COLUMN routing_json TEXT")
        conn.executemany(
            "INSERT OR IGNORE INTO departments(name) VALUES (?)",
            [(d,) for d in DEPARTMENTS],
        )
