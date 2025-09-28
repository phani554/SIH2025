# db.py
import sqlite3
import os
from typing import Optional

DB_PATH = os.getenv("DB_PATH", "db.sqlite")

def init_db():
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("""
    CREATE TABLE IF NOT EXISTS users (
      id TEXT PRIMARY KEY,
      email TEXT,
      refresh_token TEXT,
      access_token TEXT,
      token_expiry INTEGER
    );
    """)
    cur.execute("""
    CREATE TABLE IF NOT EXISTS processed_messages (
      message_id TEXT PRIMARY KEY,
      attachment_part_id TEXT,
      sha256 TEXT,
      saved_path TEXT,
      processed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    """)
    conn.commit()
    conn.close()

def save_user(user_id: str, email: Optional[str], refresh_token: str, access_token: str, expires_at: int):
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("REPLACE INTO users (id, email, refresh_token, access_token, token_expiry) VALUES (?,?,?,?,?)",
                (user_id, email, refresh_token, access_token, expires_at))
    conn.commit()
    conn.close()

def get_all_users():
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("SELECT id,email,refresh_token,access_token,token_expiry FROM users")
    rows = cur.fetchall()
    conn.close()
    return rows

def get_user_by_id(user_id: str):
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("SELECT id,email,refresh_token,access_token,token_expiry FROM users WHERE id=?", (user_id,))
    row = cur.fetchone()
    conn.close()
    return row

def save_processed_message(message_id: str, part_id: str, sha: str, saved_path: str):
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("REPLACE INTO processed_messages (message_id, attachment_part_id, sha256, saved_path) VALUES (?,?,?,?)",
                (message_id, part_id, sha, saved_path))
    conn.commit()
    conn.close()

def processed_sha_exists(sha: str) -> bool:
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("SELECT COUNT(1) FROM processed_messages WHERE sha256=?", (sha,))
    row = cur.fetchone()[0]
    conn.close()
    return row > 0

def processed_message_exists(message_id: str) -> bool:
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("SELECT COUNT(1) FROM processed_messages WHERE message_id=?", (message_id,))
    row = cur.fetchone()[0]
    conn.close()
    return row > 0

