"""SQLite storage. The same tables port to Postgres + pgvector for production.

Tables
  documents             one row per unique file (sha256 is UNIQUE -> dedupe is a DB rule)
  chunks                text pieces of a document, with their embedding
  chunks_fts            SQLite FTS5 index over chunk text, used for keyword (BM25) search
  departments           the 8 KMRL departments
  document_departments  junction: a document can concern several departments
  action_items          tasks extracted from a document
  audit_log             who did what, when (FKs use SET NULL so history survives deletes)
  gmail_accounts        OAuth refresh tokens for Gmail ingestion
"""
import sqlite3
from contextlib import contextmanager

from .config import DEPARTMENTS, settings

SCHEMA = """
CREATE TABLE IF NOT EXISTS documents (
    doc_id       INTEGER PRIMARY KEY,
    sha256       TEXT NOT NULL UNIQUE,
    file_name    TEXT NOT NULL,
    source       TEXT NOT NULL,              -- upload / gmail
    saved_path   TEXT,
    doc_type     TEXT,
    summary      TEXT,
    urgency      TEXT,
    confidence   REAL,
    status       TEXT NOT NULL DEFAULT 'NEW', -- NEW / ANALYZED / NEEDS_REVIEW / APPROVED / FAILED
    analysis_json TEXT,                       -- full validated LLM output
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
    due         TEXT
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

CREATE TABLE IF NOT EXISTS gmail_accounts (
    email         TEXT PRIMARY KEY,
    refresh_token TEXT NOT NULL,
    connected_at  TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS processed_messages (
    message_id   TEXT PRIMARY KEY,
    processed_at TEXT NOT NULL DEFAULT (datetime('now'))
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
        conn.executemany(
            "INSERT OR IGNORE INTO departments(name) VALUES (?)",
            [(d,) for d in DEPARTMENTS],
        )


def audit(conn: sqlite3.Connection, action: str, detail: str = "",
          doc_id: int | None = None, actor: str = "system") -> None:
    conn.execute(
        "INSERT INTO audit_log(doc_id, actor, action, detail) VALUES (?, ?, ?, ?)",
        (doc_id, actor, action, detail),
    )
